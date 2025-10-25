# Verilog代码生成与测试模板

这是一个用于Verilog代码生成和自动化测试的完整框架，支持基于大语言模型（LLM）的RTL代码生成和功能验证。

## 📖 项目概述

本项目提供了一套完整的Verilog代码生成流程，包含：

- **代码生成**：支持通过API调用（OpenAI、DeepSeek等）和本地LLM生成Verilog代码
- **自动化测试**：使用iverilog进行编译和仿真验证
- **性能评估**：计算pass@k指标评估代码生成质量
- **多数据集支持**：包含resbench/rtllm_v2/VerilogEval_v2三套测试数据集

## 🗂️ 项目结构

```
verilog_generate_template/
├── readme.md                    # 本文档
├── resbench/                   # ResBench数据集
│   ├── functional_correctness.py  # 功能正确性测试脚本
│   ├── generate_api.py           # API调用生成脚本
│   ├── generate_llm.py           # 本地LLM生成脚本
│   └── problems_resbench.jsonl   # 问题数据集
└── rtllm_v2/                 # RTLLM v2数据集
    ├── functional_correctness.py  # 功能正确性测试脚本
    ├── generate_api.py           # API调用生成脚本
    ├── generate_llm.py           # 本地LLM生成脚本
    ├── problems_rtllm_v2.jsonl      # 问题数据集
    └── test_file/               # 测试文件目录
└── verilogeval_v2/                 # VerilogEval v2数据集
    ├── functional_correctness.py  # 功能正确性测试脚本
    ├── generate_api.py           # API调用生成脚本
    ├── generate_llm.py           # 本地LLM生成脚本
    └── problems_verilogeval_v2.jsonl   # 问题数据集
```

## 🛠️ 环境配置

### 系统要求

- Python 3.8+
- Linux/Unix系统（推荐）
- Icarus Verilog（用于代码编译和仿真）

### 依赖安装

1. **安装Icarus Verilog**：
   ```bash
   # Ubuntu/Debian
   sudo apt-get install iverilog
   
   # CentOS/RHEL
   sudo yum install iverilog
   
   # macOS
   brew install icarus-verilog
   ```

2. **安装Python依赖**：
   ```bash
   pip install openai asyncio tqdm dataclasses
   
   # 如果使用本地LLM，还需要安装：
   pip install vllm torch transformers
   ```

## 🚀 使用指南

### 1. 数据集选择

项目包含3个数据集：

- **resbench**：包含较简单的Verilog设计问题，如基本逻辑门、多路选择器等
- **rtllm_v2**：包含更复杂的RTL级设计问题，如累加器、流水线加法器等
- **verilogeval_v2**：经典数据集

### 2. 代码生成

#### 方法一：使用API调用生成（推荐）

1. **配置API参数**：
   
   编辑 `generate_api.py` 中的配置：
   ```python
   config = {
       "api_key": "your-api-key-here",           # 您的API密钥
       "base_url": "https://api.openai.com/v1",  # API端点
       "model_name": "gpt-3.5-turbo",            # 模型名称
       "prompt_file": "problems_resbench.jsonl", # 问题文件
       "max_concurrent": 20,                     # 并发数
       "k": 5,                                   # 每个问题生成的解决方案数量
   }
   ```

2. **运行生成脚本**：
   ```bash
   # 进入对应数据集目录
   cd resbench
   
   # 运行生成脚本
   python generate_api.py
   ```

#### 方法二：使用本地LLM生成

1. **配置本地模型参数**：
   
   编辑 `generate_llm.py` 中的配置：
   ```python
   config = {
       "model_path": "/path/to/your/model",      # 本地模型路径
       "model_name": "your_model_name",          # 模型名称
       "prompt_file": "problems_resbench.jsonl", # 问题文件
       "k": 1                                    # 生成的解决方案数量
   }
   ```

2. **运行生成脚本**：
   ```bash
   # 确保有足够的GPU显存
   cd resbench
   python generate_llm.py
   ```

### 3. 功能测试

生成代码后，可以运行功能正确性测试：

1. **配置测试参数**：
   
   编辑 `functional_correctness.py` 中的文件路径：
   ```python
   SOLUTIONS_FILE = "solutions.json"           # 生成的解决方案文件
   PROBLEMS_FILE = "problems_resbench.jsonl"   # 问题数据集文件
   ```

2. **运行测试**：
   ```bash
   cd resbench  # 或 cd rtllm_v1_1
   python functional_correctness.py
   ```

3. **查看测试结果**：
   
   测试完成后将显示：
   - 每个模块的通过率
   - 整体的pass@k指标
   - 详细的错误信息

## 📊 数据格式说明

### 问题数据集格式

每行为一个JSON对象，包含：

```json
{
    "prompt": "设计要求的描述",
    "module_header": "module module_name(...);\n",
    "module_name": "模块名称", 
    "testbench": "测试台代码"
}
```

### 生成结果格式

```json
[
    {
        "module_name": "模块名称",
        "solutions": [
            {
                "solution": "生成的Verilog代码",
                "pass": "测试结果（true/false/错误信息）"
            }
        ]
    }
]
```

## 🎯 支持的模型

### API调用模式
- OpenAI GPT系列（GPT-3.5, GPT-4等）
- DeepSeek Chat
- 其他兼容OpenAI API的模型

### 本地LLM模式  
- 基于HuggingFace Transformers的模型
- 使用VLLM加速的模型
- 支持代码生成的开源模型（如CodeLlama、StarCoder等）

## 📈 评估指标

### Pass@k指标

Pass@k表示在k次尝试中至少有一次成功通过测试的概率：

- **Pass@1**：单次生成的成功率
- **Pass@5**：5次生成中至少1次成功的概率
- **Pass@10**：10次生成中至少1次成功的概率

计算公式：Pass@k = 1 - C(n-c, k) / C(n, k)

其中：
- n：总的生成样本数
- c：通过测试的样本数  
- k：评估的k值

## 🔧 自定义扩展

### 添加新的问题

1. 在JSONL文件中添加新的问题条目
2. 确保包含完整的testbench代码
3. 验证testbench的正确性

### 支持新的模型

1. 在生成脚本中添加新的模型配置
2. 根据需要调整prompt格式
3. 测试代码提取的正则表达式

### 自定义测试逻辑

1. 修改 `functional_correctness.py` 中的测试流程
2. 调整超时时间和错误处理
3. 添加新的评估指标

## ⚠️ 注意事项

1. **系统兼容性**：推荐在Linux环境下运行，Windows可能需要额外配置
2. **API限制**：注意API调用频率限制，适当调整并发数
3. **内存使用**：本地LLM模式需要足够的GPU显存
4. **超时设置**：复杂设计可能需要增加仿真超时时间
5. **文件权限**：确保临时文件的读写权限

## 🐛 常见问题

### Q: iverilog编译失败怎么办？
A: 检查Verilog代码语法，确保使用标准Verilog语法而非SystemVerilog。

### Q: API调用超时怎么处理？  
A: 减少并发数量，或者增加网络超时时间。

### Q: 本地模型显存不足？
A: 降低 `gpu_memory_utilization` 参数或使用CPU模式。

### Q: 测试结果不准确？
A: 检查testbench代码的正确性，确保测试逻辑完整。

## 📝 许可证

本项目遵循MIT许可证，详见LICENSE文件。

## 🤝 贡献

欢迎提交Issue和Pull Request来改进项目！

---

**快速开始示例**：

```bash
# 1. 安装依赖
pip install openai tqdm

# 2. 进入数据集目录  
cd resbench

# 3. 配置API密钥（编辑generate_api.py）
# 4. 生成代码
python generate_api.py

# 5. 测试生成的代码
python functional_correctness.py
```

生成完成后，检查输出的pass@k指标来评估模型性能！
