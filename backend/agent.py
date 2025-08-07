# backend/agent.py

import json
import logging
import re
import pandas as pd
from .llm_agent import llm
from .toolkits.fetch import extract_relevant_data
from .toolkits.analyze import analyze_data
from .toolkits.duckdb_runner import generate_and_run_script
from .toolkits.file_handler import extract_content

logger = logging.getLogger(__name__)

def get_plan(task_text: str) -> list:
    """
    Generates a structured, multi-step plan for which tools to run in order.
    """
    logger.info("🤖 Generating a plan...")

    tools_description = tools_description = """
- **duckdb_runner.generate_and_run_query(task: str)**: 
  - **Use Case**: Use for any task that requires querying a large dataset (e.g., on S3). This tool will autonomously generate and execute the necessary SQL.
  - **Input**: The `tool_input` should be a clear and specific string describing the task for this step.

- **fetch.extract_relevant_data(url: str, task_description: str)**: 
  - **Use Case**: Use for scraping a standard webpage URL.
  - **Input**: The `tool_input` should be a JSON object with "url" and "task_description" keys.

- **analyze.analyze_data(data_context: dict, task: str)**: 
  - **Use Case**: Use for complex Python-based analysis on data already loaded by a previous step.
  - **Input**: The `tool_input` should be the user's original task description string.
"""

    prompt = f"""
You are an Expert AI Planner. Your role is to create the most logical and efficient plan to solve the user's task by using the available tools.

**User's Task:**
---
{task_text}
---

**Available Tools:**
---
{tools_description}
---


**Strategy Guide:**
- **For Web Scraping Tasks:** Always create a two-step plan.
    1.  **`fetch` step:** Write a simple script to get the raw data. The most robust code is usually `result = pd.read_html(url)[0]`.
    2.  **`analyze` step:** Write a comprehensive script to perform ALL data cleaning, analysis, calculations, and plotting. This script should anticipate messy data (e.g., complex column names, non-numeric values) and clean it before performing the analysis.

**CRITICAL Instructions:**
1.  **Use Provided URLs/Paths:** If the user's task includes a URL (like `https://...` or `s3://...`), you MUST use that exact URL/path in the tools you call. DO NOT invent or assume a different one.
2.  **Create a Plan:** Create a step-by-step plan using one or more of the available tools.
3.  **Output Format:** Your output MUST be a valid JSON list of dictionaries. Each dictionary must have "tool_name", "tool_input", and a unique "step_name".

**YOUR PLAN (as a JSON list):**
"""
    
    try:
        plan_str = llm(prompt).strip()
        match = re.search(r'\[\s*\{.*\}\s*\]', plan_str, re.DOTALL)
        if not match:
            raise ValueError("LLM did not return a valid JSON list.")
        
        plan = json.loads(match.group(0))
        logger.info(f"✅ Plan generated successfully: {plan}")
        return plan
    except Exception as e:
        logger.error(f"❌ Failed to generate or parse a valid plan: {e}")
        raise RuntimeError("The AI failed to generate a valid execution plan.")


def handle_task(task_text: str, attachments: dict = None, max_global_retries: int = 1) -> dict:
    """
    Main agent logic that generates a plan and orchestrates the autonomous tools.
    """
    logger.info("📥 Received task: %s", task_text.strip())
    full_task_text = task_text.strip()

    for attempt in range(max_global_retries):
        logger.info(f"--- Starting Agent Execution: Attempt {attempt + 1} of {max_global_retries} ---")
        
        results = {
            "task": full_task_text,
            "reasoning": "Planner-based execution with autonomous tools. See logs for details.",
            "dataframe_preview": "",
            "final_answers": None,
            "error": None
        }

        try:
            plan = get_plan(full_task_text)
            data_context = {}
            
            for i, step in enumerate(plan):
                tool_name = step.get("tool_name")
                tool_input = step.get("tool_input")
                step_name = step.get("step_name", f"step_{i+1}")
                
                logger.info(f"--- Step {i+1} ({step_name}): Executing Tool: {tool_name} ---")

                step_result = None
                if tool_name == "duckdb_runner.generate_and_run_query":
                    if not isinstance(tool_input, str):
                        raise TypeError(f"Expected a string for duckdb_runner input, but got {type(tool_input)}")

                    # task_for_tool = tool_input.get("task")
                    # if not task_for_tool:
                    #     raise ValueError("Plan for 'duckdb_runner' tool is missing a 'task' in its input.")

                    step_result = generate_and_run_script(task=tool_input, full_task_context=full_task_text)

                elif tool_name == "fetch.extract_relevant_data":
                    if not isinstance(tool_input, dict):
                        raise TypeError(f"Expected a dictionary for fetch tool input, but got {type(tool_input)}")
                    url = tool_input.get("url")
                    task_desc = tool_input.get("task_description")
                    if not url:
                        raise ValueError("Plan for 'fetch' tool is missing a URL.")
                    step_result = extract_relevant_data(url, task_desc)

                elif tool_name == "analyze.analyze_data":
                    step_result = analyze_data(data_context, full_task_text)
                
                else:
                    raise ValueError(f"Unknown tool in plan: {tool_name}")

                data_context[step_name] = step_result

                if isinstance(step_result, pd.DataFrame):
                    results["dataframe_preview"] += f"\n--- Preview for Step: {step_name} ---\n{step_result.head().to_markdown()}"
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
