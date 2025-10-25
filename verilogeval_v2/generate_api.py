import json
import os
import asyncio
import re
from typing import Dict, Any, List
from tqdm.asyncio import tqdm as async_tqdm
from openai import OpenAI
from dataclasses import dataclass

# 设置工作目录为当前文件所在目录
os.chdir(os.path.dirname(os.path.abspath(__file__)))

@dataclass
class Problem:
    prompt: str
    module_header: str
    module_name: str


class VerilogGenerator:
    def __init__(self, api_key: str, base_url: str, model_name: str):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model_name = model_name

    def _agent_call(self, messages, k):
        temperature = 0 if k == 1 else 0.6
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=temperature,
            stream=False,
        )
        content = response.choices[0].message.content
        return content

    def _create_prompt(self, problem: Problem) -> str:
        return f"""Here we assume the SystemVerilog is not supported, so don't use the SystemVerilog syntax, such as break statement.
Please write a Verilog module that solves the following problem efficiently, using the exact module header below:

Problem:
{problem.prompt}

Module header (must not be changed):
{problem.module_header}

Return only the verilog code, no any explanation.

such as:
```verilog
code_here
```
        """

    async def _call_llm(self, prompt: str, k: int) -> str:
        messages = [{"role": "user", "content": prompt}]
        output_content = await asyncio.to_thread(
            self._agent_call, messages, k
        )
        return output_content

    def _extract_verilog_code(self, content: str) -> str:
        code_block_pattern = r"```verilog\n([\s\S]*?)\n```"
        match = re.search(code_block_pattern, content, re.IGNORECASE)
        return match.group(1) if match else content

    async def process_problem(self, problem: Problem, k: int) -> List[Dict[str, Any]]:
        prompt = self._create_prompt(problem)
        # output_content = await self._call_llm(prompt)
        # verilog_code = self._extract_verilog_code(output_content)

        # return {"solution": verilog_code, "pass": "", "resource_usage": ""}
        solutions = []
        for _ in range(k):
            output_content = await self._call_llm(prompt, k)
            verilog_code = self._extract_verilog_code(output_content)
            solutions.append({"solution": verilog_code, "pass": ""})

        result = {
            "module_name": problem.module_name,
            "solutions": solutions
        }

        return result

async def main(config):
    # 初始化组件
    generator = VerilogGenerator(
        config["api_key"], config["base_url"], config["model_name"]
    )

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

    # 创建信号量限制并发
    semaphore = asyncio.Semaphore(config["max_concurrent"])

    # 处理问题
    async def process_with_semaphore(problem: Problem):
        async with semaphore:
            return await generator.process_problem(problem, config["k"])

    # 并发处理所有问题
    all_results = await async_tqdm.gather(
        *[process_with_semaphore(problem) for problem in all_problems],
        desc="Processing all problems",
    )

    # 保存结果
    output_file_name = f"pass{config['k']}_{config['model_name']}.json"
    with open(output_file_name, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":

    config = {
        "api_key": "sk-",
        "base_url": "https://api.openai-proxy.org/v1",
        "model_name": "gpt-3.5-turbo",
        "prompt_file": "problems_verilogeval_v2.jsonl",
        "max_concurrent": 20,
        "k": 1,
    }

    asyncio.run(main(config))

