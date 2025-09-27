import json
import os
import re
from typing import Dict, Any, List
from dataclasses import dataclass
from tqdm import tqdm
from vllm import LLM, SamplingParams


@dataclass
class Problem:
    prompt: str
    module_header: str
    module_name: str


class LocalVerilogGenerator:
    def __init__(self, model_path: str, max_tokens: int = 2048):
        """Initialize the generator with local LLM using vllm"""
        self.model = LLM(model=model_path, gpu_memory_utilization=0.9, max_model_len=4096, trust_remote_code=True)
        self.max_tokens = max_tokens

    def _create_prompt(self, problem: Problem) -> str:
        return f"""### Instruct: Please act as a professional Verilog designer and provide Verilog code based on the given instruction. {problem.prompt}

### Response: ```verilog
{problem.module_header}
"""

    def generate_solutions(self, problems: List[Problem], k: int) -> List[Dict[str, Any]]:
        """Generate k solutions for multiple problems using local LLM with vllm"""
        prompts = [self._create_prompt(problem) for problem in problems]
        temperature = 0 if k == 1 else 0.6
        # Configure sampling parameters
        sampling_params = SamplingParams(
            temperature=temperature,
            max_tokens=self.max_tokens,
            n=k  # Generate k samples for each prompt
        )

        # Generate samples for all prompts at once
        outputs = self.model.generate(
            prompts=prompts,
            sampling_params=sampling_params
        )
        all_solutions = []
        # Process each generated output
        for i, output in enumerate(outputs):
            problem = problems[i]
            solutions = []
            for sample in output.outputs:
                generated_text = sample.text
                verilog_code = self._extract_verilog_code(generated_text)
                verilog_code = problem.module_header + '\n    ' + verilog_code
                solutions.append({"solution": verilog_code, "pass": ""})
            result = {
                "module_name": problem.module_name,
                "solutions": solutions
            }
            all_solutions.append(result)

        return all_solutions

    def _extract_verilog_code(self, content: str) -> str:
        if '```' in content:
            result = content.split('```')[0].strip()
        else:
            result = content
        return result

def generate_solutions(config):
    # Initialize the local model generator
    generator = LocalVerilogGenerator(model_path=config["model_path"])

    all_problems = []
    # 加载问题数据
    with open(config["prompt_file"], "r", encoding="utf-8") as f:
        for line in f:
            item = json.loads(line)
            problem = Problem(
                prompt=item.get("prompt", ""),
                module_header=item.get("module_header", ""),
                module_name=item.get("module_name", ""),
            )
            all_problems.append(problem)

    print(f"Generating {config['k']} solutions for {len(all_problems)} problems...")

    # Generate solutions
    all_solutions = generator.generate_solutions(all_problems, config["k"])

    # 保存结果
    with open(config["output_file"], "w", encoding="utf-8") as f:
        json.dump(all_solutions, f, ensure_ascii=False, indent=4)

    print(f"All solutions generated and saved to {config['output_file']}")


if __name__ == "__main__":
    # Configuration
    config = {
        "model_path": "/media/yg/E/models/OriGen_merged",  # Path to your local HF model
        "model_name": "origen",  # Name to use in the JSON output
        "prompt_file": "problems_rtllm.jsonl",
        "output_file": "pass5_origen.json",
        "k": 5  # Number of solutions to generate per problem
    }
    # Run only the generation part
    generate_solutions(config)