import json
import os
import re
import subprocess
import math
from collections import defaultdict
from tqdm import tqdm

# 设置工作目录为当前文件所在目录
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# ================== 配置文件路径 ==================
SOLUTIONS_FILE = "pass1_gpt-3.5-turbo.json"    # 生成的解决方案文件
PROBLEMS_FILE = "problems_rtllm_v2.jsonl"       # 问题数据集文件
TEMP_VERILOG_FILE = "temp.v"                    # 临时Verilog设计文件
TEMP_TESTBENCH_FILE = "testbench.v"             # 临时测试台文件
VVP_OUTPUT_FILE = "test.vvp"                    # 编译输出文件

def extract_testbench_module_name(testbench_content):
    """
    从测试台代码中提取顶层模块名称
    
    参数:
        testbench_content (str): 测试台代码内容
        
    返回:
        str: 测试台模块名称，如果未找到则返回None
        
    说明:
        通过正则表达式匹配 "module 模块名" 的模式来提取测试台的顶层模块名
    """
    for line in testbench_content.splitlines():
        line = line.strip()
        # 匹配module声明行: module <name> (...) 或 module <name>;
        match = re.search(r'\s*module\s+(\w+)\s*[\(;]', line)
        if match:
            return match.group(1)
    return None

def calculate_pass_at_k(n, c, k):
    """
    计算pass@k指标
    
    参数:
        n: 总样本数量
        c: 通过测试的样本数量  
        k: pass@k中的k值
        
    返回:
        float: pass@k概率值
        
    说明:
        pass@k表示在k次尝试中至少有一次成功的概率
        公式: pass@k = 1 - C(n-c, k) / C(n, k)
    """
    if n == 0:
        return 0.0
    
    if c == 0:
        return 0.0
    
    if k >= n:
        return 1.0 if c > 0 else 0.0
    
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)

def clean_up_simulation():
    """
    清理仿真环境
    
    功能:
        1. 终止所有挂起的仿真进程
        2. 删除所有临时文件
    """
    print("正在终止所有挂起的仿真进程...")
    
    # 终止iverilog和vvp进程
    subprocess.run("pkill iverilog", shell=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    subprocess.run("pkill vvp", shell=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    
    # 清理临时文件
    temp_files = [TEMP_VERILOG_FILE, TEMP_TESTBENCH_FILE, VVP_OUTPUT_FILE]
    for file in temp_files:
        if os.path.exists(file):
            os.remove(file)
            print(f"已删除临时文件: {file}")

def run_functional_correctness():
    """
    运行功能正确性测试
    
    主要流程:
        1. 加载解决方案和问题数据
        2. 对每个解决方案进行编译和仿真测试
        3. 记录测试结果和统计信息
        4. 计算并输出pass@k指标
        
    注意:
        此版本使用动态提取的测试台模块名，并通过检查输出中的
        "All tests passed" 或 "Your Design Passed" 来判断测试结果
    """
    print("开始加载数据文件...")
    
    # ================== 加载数据文件 ==================
    # 加载生成的解决方案JSON文件
    try:
        with open(SOLUTIONS_FILE, "r", encoding="utf-8") as file:
            solutions_data = json.load(file)
        print(f"成功加载解决方案文件: {SOLUTIONS_FILE}")
    except FileNotFoundError:
        print(f"错误: 找不到解决方案文件 {SOLUTIONS_FILE}")
        return
    except json.JSONDecodeError:
        print(f"错误: 解决方案文件 {SOLUTIONS_FILE} 格式错误")
        return

    # 加载问题数据JSONL文件
    problems_data = []
    try:
        with open(PROBLEMS_FILE, "r", encoding="utf-8") as file:
            for line_num, line in enumerate(file, 1):
                try:
                    problems_data.append(json.loads(line))
                except json.JSONDecodeError:
                    print(f"警告: 第{line_num}行数据格式错误，跳过")
        print(f"成功加载问题数据文件: {PROBLEMS_FILE}，共{len(problems_data)}个问题")
    except FileNotFoundError:
        print(f"错误: 找不到问题数据文件 {PROBLEMS_FILE}")
        return
            
    # 构建模块名到测试台的映射
    module_testbenches = {}
    for problem in problems_data:
        module_name = problem.get("module_name")
        testbench = problem.get("testbench")
        if module_name and testbench:
            module_testbenches[module_name] = testbench
    
    print(f"成功构建测试台映射，共{len(module_testbenches)}个模块")

    # ================== 初始化测试环境 ==================
    # 用于统计pass@k结果
    module_results = defaultdict(lambda: {"total": 0, "passed": 0})
    
    # 设置仿真超时时间（秒）
    timeout = 5
    
    print("开始执行功能正确性测试...")
    
    # ================== 主测试循环 ==================
    for module_entry in tqdm(solutions_data, desc="测试进度"):
        module_name = module_entry.get("module_name")
        if not module_name or module_name not in module_testbenches:
            print(f"警告: 模块 {module_name} 没有对应的测试台，跳过")
            continue

        testbench_code = module_testbenches[module_name]
        solutions = module_entry.get("solutions", [])
        
        # 遍历当前模块的所有解决方案
        for solution_idx, solution_entry in enumerate(solutions):
            # 统计总的解决方案数量
            module_results[module_name]["total"] += 1

            verilog_code = solution_entry.get("solution", "")
            if not verilog_code:
                solution_entry["pass"] = "错误: 解决方案为空"
                continue

            # ================== 准备测试文件 ==================
            # 写入Verilog设计文件
            try:
                with open(TEMP_VERILOG_FILE, "w", encoding="utf-8") as f:
                    f.write(verilog_code)
            except IOError as e:
                solution_entry["pass"] = f"文件写入错误: {str(e)}"
                continue

            # 写入测试台文件
            try:
                with open(TEMP_TESTBENCH_FILE, "w", encoding="utf-8") as f:
                    f.write(testbench_code)
            except IOError as e:
                solution_entry["pass"] = f"测试台文件写入错误: {str(e)}"
                continue

            # ================== 提取测试台模块名 ==================
            # 动态提取测试台的顶层模块名
            tb_module = extract_testbench_module_name(testbench_code)
            if not tb_module:
                solution_entry["pass"] = "错误: 无法从测试台中提取模块名"
                print(f"警告: 无法从模块 {module_name} 的测试台中提取模块名，跳过")
                continue

            # ================== 编译阶段 ==================
            # 构建iverilog编译命令
            compile_cmd = [
                "iverilog",                    # 编译器
                "-Wall",                       # 显示所有警告
                "-Winfloop",                   # 检测无限循环
                "-Wno-timescale",             # 忽略时间尺度警告
                "-g2012",                     # 使用Verilog-2012标准
                "-s", tb_module,              # 指定顶层模块（动态提取的）
                "-o", VVP_OUTPUT_FILE,        # 输出文件
                TEMP_VERILOG_FILE,            # 设计文件
                TEMP_TESTBENCH_FILE           # 测试台文件
            ]

            # 执行编译
            compile_process = subprocess.run(compile_cmd, capture_output=True, text=True)

            # 检查编译是否成功
            if compile_process.returncode != 0:
                compile_error = compile_process.stderr.strip()
                solution_entry["pass"] = f"编译失败: {compile_error}"
                continue

            # ================== 仿真阶段 ==================
            # 构建仿真命令
            sim_cmd = ["vvp", "-n", VVP_OUTPUT_FILE]
            
            try:
                # 执行仿真（带超时）
                sim_process = subprocess.run(sim_cmd, capture_output=True, text=True, timeout=timeout)
                output_log = sim_process.stdout
                error_log = sim_process.stderr
            except subprocess.TimeoutExpired:
                # 仿真超时
                output_log = "超时"
                error_log = "仿真超时"
            except Exception as e:
                # 其他异常
                output_log = "异常"
                error_log = f"仿真异常: {str(e)}"

            # ================== 结果分析 ==================
            # 检查输出中是否包含成功标识
            # RTLLM数据集使用 "All tests passed" 或 "Your Design Passed" 作为成功标识
            test_passed = ("All tests passed" in output_log or 
                          "Your Design Passed" in output_log)

            if test_passed:
                # 测试通过
                solution_entry["pass"] = "true"
                module_results[module_name]["passed"] += 1
            else:
                # 测试失败，记录详细错误信息
                if error_log and error_log != "":
                    solution_entry["pass"] = f"仿真错误: {error_log.strip()}"
                elif "超时" in output_log:
                    solution_entry["pass"] = "测试失败: 仿真超时"
                else:
                    solution_entry["pass"] = "测试失败: 未通过测试用例"

            # ================== 保存中间结果 ==================
            # 每测试完一个解决方案就保存结果，防止意外中断导致数据丢失
            try:
                with open(SOLUTIONS_FILE, "w", encoding="utf-8") as file:
                    json.dump(solutions_data, file, indent=4, ensure_ascii=False)
            except IOError as e:
                print(f"警告: 保存结果文件失败: {str(e)}")

    # ================== 清理环境 ==================
    clean_up_simulation()
    
    # ================== 计算和输出统计结果 ==================
    print("\n" + "="*50)
    print("测试完成，正在计算统计结果...")
    
    # 确定k值（假设所有模块的解决方案数量相同）
    first_module = next(iter(module_results.values()), {"total": 0})
    k_value = first_module["total"]
    
    if k_value == 0:
        print("错误: 没有找到任何解决方案，无法计算pass@k指标")
        return
    
    # 计算每个模块的pass@k
    total_modules = 0
    total_pass_at_k = 0
    
    print(f"\n各模块详细结果 (pass@{k_value}):")
    print("-" * 60)
    print(f"{'模块名':<20} {'通过/总数':<12} {'通过率':<10} {'pass@k':<10}")
    print("-" * 60)
    
    for module_name, result in sorted(module_results.items()):
        n = result["total"]          # 总样本数
        c = result["passed"]         # 通过样本数
        
        if n > 0:
            pass_rate = c / n                              # 通过率
            pass_at_k = calculate_pass_at_k(n, c, k_value) # pass@k值
            
            total_modules += 1
            total_pass_at_k += pass_at_k
            
            print(f"{module_name:<20} {c}/{n:<11} {pass_rate:<10.3f} {pass_at_k:<10.4f}")
    
    # 计算并输出平均pass@k
    print("-" * 60)
    if total_modules > 0:
        avg_pass_at_k = total_pass_at_k / total_modules
        print(f"平均pass@{k_value} (共{total_modules}个模块): {avg_pass_at_k:.4f}")
    else:
        print("没有可用的模块数据，无法计算平均pass@k")
    
    print("="*50)
    print("所有测试已完成！")

if __name__ == "__main__":
    """
    程序入口点
    
    使用方法:
        python functional_correctness.py
        
    注意事项:
        1. 确保已安装iverilog仿真器
        2. 确保SOLUTIONS_FILE和PROBLEMS_FILE文件存在
        3. 本版本使用动态测试台模块名提取
        4. 测试成功判断基于输出中的"All tests passed"或"Your Design Passed"
        5. 程序会在当前目录生成临时文件，测试完成后会自动清理
    """
    print("RTLLM v2 Verilog功能正确性测试程序")
    print("="*50)
    
    try:
        run_functional_correctness()
    except KeyboardInterrupt:
        print("\n用户中断程序执行")
        clean_up_simulation()
    except Exception as e:
        print(f"\n程序执行出现错误: {str(e)}")
        clean_up_simulation()
        raise