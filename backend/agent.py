# backend/agent.py

import json
import logging
import re
import pandas as pd
from .llm_agent import llm
from .toolkits.fetch import execute_fetch
from .toolkits.analyze import execute_analysis
from .toolkits.duckdb_runner import execute_query
from .toolkits.file_handler import extract_content

logger = logging.getLogger(__name__)

def get_plan_with_code(task_text: str) -> list:
    """
    Generates a structured plan where the LLM writes the code for each step.
    """
    logger.info("🤖 Generating a plan with executable code...")

    tools_description = tools_description = """
- **duckdb_runner**:
  - **Use Case**: Best for querying large, structured datasets (e.g., Parquet files on S3). Ideal for filtering, aggregating, joining, and performing calculations directly on the data at its source.
  - **Strengths**: Extremely fast for large-scale data operations. Use this to "push down" computation and only retrieve the specific data you need for analysis.
  - **Input**: The `tool_input` must be a single, complete, and valid DuckDB SQL query string.
  - **Returns**: A pandas DataFrame.

- **fetch**:
  - **Use Case**: Use for scraping data from a single, standard webpage URL (e.g., a Wikipedia article).
  - **Strengths**: Good for extracting tables or text from HTML content.
  - **Input**: The `tool_input` must be a JSON object with three keys: "url", "task", and "code".
  - **Code Instructions**: The `code` should be a Python script that uses the pre-defined `url` variable. The most robust method is `tables = pd.read_html(url)`. The script must find the correct table from the `tables` list and assign the final, raw pandas DataFrame to a variable named `result`.
  - **Returns**: A pandas DataFrame.

- **analyze**:
  - **Use Case**: This is the primary tool for performing complex analysis in Python. Use it for tasks that are difficult or impossible in SQL, such as statistical modeling, creating visualizations (plots), or complex data cleaning and transformation.
  - **Strengths**: Can synthesize results from multiple previous steps. It has access to a `data_context` dictionary containing the outputs of all prior steps.
  - **Input**: The `tool_input` must be a JSON object with two keys: "task" and "code".
  - **Code Instructions**: The `code` should be a Python script. It must access the data from previous steps using the `data_context` dictionary (e.g., `df = data_context['step_1_result']`). The script should perform all necessary cleaning, calculations, and plotting. The script MUST assign the final answer to a variable named `result`.
  - **Returns**: The final answer. The format of the answer **must match the format requested in the user's task** (e.g., a JSON object, a JSON array of strings). If no specific format is requested, the default return type is a Python `list`.
"""

    prompt = f"""
You are an Expert Data analyst agent, AI Planner and Coder. Your role is to create the most logical and efficient multi-step plan to solve the user's task by writing the executable code for each step.

**User's Task:**
---
{task_text}
---

**Available Tools & Use Cases:**
---
{tools_description}
---

**Instructions:**
1.  Break down the user's task into logical steps.
2.  For each step, choose the appropriate tool (`duckdb_runner`, `fetch`, or `analyze`).
3.  **Write the complete, executable code** (either SQL or Python) for the `tool_input` of each step.
4.  Your output MUST be a valid JSON list of dictionaries, each with "tool_name", "tool_input", and a unique "step_name".
5.  **CRITICAL Input Formatting:**
    - For `duckdb_runner`, the `tool_input` must be a single SQL string.
    - For `fetch`, the `tool_input` MUST be a JSON object with three keys: "url", "task", and "code".
    - For `analyze`, the `tool_input` MUST be a JSON object with two keys: "task" and "code".
6.  **CRITICAL:** The Python code you write must be a simple, top-level script. **DO NOT wrap your code in a function definition (e.g., `def my_function(): ...`)**. The script MUST assign its final output to a variable named `result`.
7.  IMPORTANT: import the libraries inside the function as the exec() function is used in the tools for execution and it does not support imports outside the function scope.

**return YOUR PLAN as a JSON object**
**Example Plan:**
```json
[
  {{
    "tool_name": "duckdb_runner",
    "step_name": "get_case_counts",
    "tool_input": "INSTALL httpfs; LOAD httpfs; INSTALL parquet; LOAD parquet; SELECT court, COUNT(*) AS case_count FROM read_parquet('s3://indian-high-court-judgments/metadata/parquet/year=2022/court=*/bench=*/metadata.parquet?s3_region=ap-south-1') GROUP BY court;"
  }},
  {{
    "tool_name": "analyze",
    "step_name": "calculate_average",
    "tool_input": {{
      "task": "From the case counts, find the top 5 courts and calculate their average number of cases.",
      "code": "import pandas as pd\\n\\ndf = data_context['get_case_counts']\\ndf_sorted = df.sort_values(by='case_count', ascending=False)\\ntop_5_avg = df_sorted.head(5)['case_count'].mean()\\nresult = f'The average number of cases for the top 5 courts is {{top_5_avg:.2f}}'"
    }}
  }}
]
```
 """

    try:
        plan_str = llm(prompt).strip()
        match = re.search(r'\[\s*\{.*\}\s*\]', plan_str, re.DOTALL)
        if not match:
            raise ValueError("LLM did not return a valid JSON list.")
        
        json_str = match.group(0)

        plan = json.loads(json_str)
        logger.info(f"✅ Plan with code generated successfully: {plan}")
        return plan
    except Exception as e:
        logger.error(f"❌ Failed to generate or parse a valid plan: {e}")
        raise RuntimeError("The AI failed to generate a valid execution plan.")


def handle_task(task_text: str, attachments: dict = None, max_global_retries: int = 1) -> dict:
    """
    Main agent logic that gets a plan with pre-written code and orchestrates the tools.
    """
    logger.info("📥 Received task: %s", task_text.strip())
    full_task_text = task_text.strip()

    for attempt in range(max_global_retries):
        logger.info(f"--- Starting Agent Execution: Attempt {attempt + 1} of {max_global_retries} ---")
        
        execution_log = []
        
        results = {
            "task": full_task_text,
            "reasoning": None,
            "dataframe_preview": "",
            "final_answers": None,
            "error": None,
            "execution_log": execution_log
        }

        try:
            plan = get_plan_with_code(full_task_text)
            results["reasoning"] = json.dumps(plan, indent=2)
            
            data_context = {}
            
            for i, step in enumerate(plan):
                tool_name = step.get("tool_name")
                tool_input = step.get("tool_input")
                step_name = step.get("step_name", f"step_{i+1}")
                
                logger.info(f"--- Step {i+1} ({step_name}): Executing Tool: {tool_name} ---")

                step_result = None
                if tool_name == "duckdb_runner":
                    step_result = execute_query(code=tool_input, task=full_task_text, execution_log=execution_log)
                
                elif tool_name == "fetch":
                    if not isinstance(tool_input, dict):
                        raise TypeError(f"Expected a dictionary for fetch tool input, but got {type(tool_input)}")
                    code = tool_input.get("code")
                    url = tool_input.get("url")
                    task = tool_input.get("task", full_task_text)
                    step_result = execute_fetch(code=code, url=url, task=task, execution_log=execution_log)

                elif tool_name == "analyze":
                    if not isinstance(tool_input, dict):
                        raise TypeError(f"Expected a dictionary for analyze tool input, but got {type(tool_input)}")
                    code = tool_input.get("code")
                    task = tool_input.get("task", full_task_text)
                    step_result = execute_analysis(code=code, data_context=data_context, task=task, execution_log=execution_log)
                
                else:
                    raise ValueError(f"Unknown tool in plan: {tool_name}")

                data_context[step_name] = step_result

                if isinstance(step_result, pd.DataFrame):
                    results["dataframe_preview"] += f"\n--- Preview for Step: {step_name} ---\n{step_result.head().to_markdown()}"
                else:
                    if isinstance(step_result, dict):
                        results["final_answers"] = json.dumps(step_result, indent=2)
                    else:
                        results["final_answers"] = step_result


            logger.info("✅✅✅ Task completed successfully on global attempt %d!", attempt + 1)
            return results

        except Exception as e:
            logger.error(f"🔥🔥🔥 Agent execution failed on attempt {attempt + 1}: {e}", exc_info=True)
            results["error"] = str(e)
            if attempt + 1 == max_global_retries:
                logger.error("❌ Agent failed on all attempts.")
                return results
            logger.warning("⚠️ Retrying entire agent execution from the beginning...")

    return results
