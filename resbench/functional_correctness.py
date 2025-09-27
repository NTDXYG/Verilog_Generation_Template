import json
import os
import re
import subprocess
import math
from collections import defaultdict
from tqdm import tqdm

# 设置工作目录为当前文件所在目录
os.chdir(os.path.dirname(os.path.abspath(__file__)))
# File paths
SOLUTIONS_FILE = "vcd_rnk_no_syntax_gpt_3.5_rerank_n1.json"
PROBLEMS_FILE = "problems_resbench.jsonl"
TEMP_VERILOG_FILE = "temp.v"
TEMP_TESTBENCH_FILE = "testbench.v"
VVP_OUTPUT_FILE = "test.vvp"

# Function to extract the testbench module name from the testbench file
def extract_testbench_module_name(testbench_content):
    for line in testbench_content.splitlines():
        line = line.strip()
        match = re.search(r'\s*module\s+(\w+)\s*[\(;]', line)
        if match:
            return match.group(1)
    return None

def calculate_pass_at_k(n, c, k):
    """
    Calculate pass@k metric
    n: number of samples
    c: number of correct samples
    k: k value for pass@k
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
    Kill all simulation processes.
    """
    print("Killing all hanging simulation processes.")
    subprocess.run("pkill iverilog", shell=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    subprocess.run("pkill vvp", shell=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    
    # Clean up temporary files
    for file in [TEMP_VERILOG_FILE, TEMP_TESTBENCH_FILE, VVP_OUTPUT_FILE]:
        if os.path.exists(file):
            os.remove(file)

def run_functional_correctness():
    # Load JSON file for solutions
    with open(SOLUTIONS_FILE, "r", encoding="utf-8") as file:
        solutions_data = json.load(file)

    # Load JSONL file for problems
    problems_data = []
    with open(PROBLEMS_FILE, "r", encoding="utf-8") as file:
        for line in file:
            problems_data.append(json.loads(line))
            
    module_testbenches = {}
    for problem in problems_data:
        module_testbenches[problem["module_name"]] = problem["testbench"]

    # Rest of the function remains the same...
    # For pass@k calculation
    module_results = defaultdict(lambda: {"total": 0, "passed": 0})
    
    # Set timeout for simulations
    timeout = 5  # 5 seconds timeout
        
    for module_entry in tqdm(solutions_data, desc="Testing models"):
        module_name = module_entry["module_name"]
        if module_name not in module_testbenches:
            continue

        testbench_code = module_testbenches[module_name]
        solutions = module_entry["solutions"]
        
        # Iterate over all solutions
        for solution_entry in solutions:

            # Track total number of solutions for pass@k
            module_results[module_name]["total"] += 1

            verilog_code = solution_entry["solution"]

            # Write the Verilog design to a file
            with open(TEMP_VERILOG_FILE, "w", encoding="utf-8") as f:
                f.write(verilog_code)

            # Write the testbench to a file
            with open(TEMP_TESTBENCH_FILE, "w", encoding="utf-8") as f:
                f.write(testbench_code)

            # Extract the testbench module name
            tb_module = extract_testbench_module_name(testbench_code)
            if not tb_module:
                # print(f"Error: Could not extract testbench module from {module_name}. Skipping...")
                solution_entry["pass"] = "Error: Could not extract testbench module."
                continue

            # print(f"Testing module: {module_name} (Testbench: {tb_module})")

            # Run iverilog compilation
            # print(f"Compiling Verilog for {module_name}...")
            compile_cmd = [
                "iverilog",
                "-Wall",
                "-Winfloop",
                "-Wno-timescale",
                "-g2012",
                "-s", tb_module,
                "-o", VVP_OUTPUT_FILE,
                TEMP_VERILOG_FILE,
                TEMP_TESTBENCH_FILE
            ]

            compile_process = subprocess.run(compile_cmd, capture_output=True, text=True)

            # Check if compilation was successful
            if compile_process.returncode != 0:
                compile_error = compile_process.stderr
                solution_entry["pass"] = f"Compilation failed: {compile_error}"
                # print(f"Compilation failed for {module_name}: {compile_error}")
                continue

            # Run simulation
            # print(f"Running simulation for {module_name}...")
            sim_cmd = ["vvp", "-n", VVP_OUTPUT_FILE]

            try:
                sim_process = subprocess.run(sim_cmd, capture_output=True, text=True, timeout=timeout)
                # Capture output logs
                output_log = sim_process.stdout
                error_log = sim_process.stderr
            except:
                # Capture output logs
                output_log = "Timeout"
                error_log = "Timeout"


            # Determine pass/fail status (assuming "All tests passed" or "Your Design Passed" is in output)
            test_passed = "All tests passed" in output_log or "Your Design Passed" in output_log

            if test_passed:
                solution_entry["pass"] = "true"
                module_results[module_name]["passed"] += 1
            else:
                # Check for specific failure messages
                if error_log:
                    solution_entry["pass"] = f"Simulation error: {error_log}"
                else:
                    solution_entry["pass"] = "Test failed: tests did not pass"

            # print(f"Test result for {module_name}: {'PASS' if test_passed else 'FAIL'}")
            # print(f"Output: {output_log}")

            # if error_log:
            #     print(f"Errors: {error_log}")

            # Save results after testing each module
            with open(SOLUTIONS_FILE, "w", encoding="utf-8") as file:
                json.dump(solutions_data, file, indent=4)


    # Clean up any hanging simulation processes
    clean_up_simulation()
    
    # Calculate and print pass@k results
    # Determine k value from first module's solutions count (assuming all modules have the same k)
    first_module = next(iter(module_results.values()), {"total": 0})
    k_value = first_module["total"]
    
    if k_value == 0:
        print("No solutions found. Cannot calculate pass@k.")
        return
    
    # Calculate pass@k for each module
    total_modules = 0
    total_pass_at_k = 0
    
    for module_name, result in sorted(module_results.items()):
        n = result["total"]
        c = result["passed"]
        if n > 0:
            pass_at_k = calculate_pass_at_k(n, c, k_value)
            total_modules += 1
            total_pass_at_k += pass_at_k
    
    # Calculate and print average pass@k
    if total_modules > 0:
        avg_pass_at_k = total_pass_at_k / total_modules
        print(f"\nAverage pass@{k_value} across {total_modules} modules: {avg_pass_at_k:.4f}")
    else:
        print("\nNo modules with solutions. Cannot calculate average pass@k.")
    
    print("All tests completed.")

if __name__ == "__main__":
    run_functional_correctness()
