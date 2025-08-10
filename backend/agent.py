# backend/agent.py

import json
import logging
import re
import pandas as pd
from .llm_agent import llm
from .toolkits.fetch import extract_relevant_data
from .toolkits.analyze import analyze_data
from .toolkits.duckdb_runner import retrieve_data_as_df
from .toolkits.file_handler import handle_file_task

logger = logging.getLogger(__name__)

def get_plan(task_text: str, file_context: str = "") -> list:
    """
    Generates a structured, multi-step plan for which tools to run in order.
    """
    logger.info("🤖 Generating a plan...")

    tools_description = """
- **file_handler.handle_file_task(task_description: str, full_task: str, file_path: str)**:
    - **Use Case**: Use this tool to extract data, tables, text, or images from any uploaded file (CSV, Excel, PDF, image, etc.). It can read, preview, and extract content from files, and generate Python code to process the file as per the task description.
    - **Input Parameters (as dictionary):**
        - `task_description` (str): A concise, specific instruction for what to extract or process from the file (e.g., "Extract all tables as pandas DataFrames", "Extract all text from the PDF", "Extract the first image from the file").
        - `full_task` (str): The full user request, including background and requirements.
        - `file_path` (str): The logical name of the uploaded file (e.g., "q1.csv", "data.xlsx").
    - **Returns**: If the file contains tables (CSV, Excel, or tables in PDF), returns a pandas DataFrame. For text or images, returns the extracted content in a suitable format (string, base64 image, etc.).
    - **How to use in a plan:**
        - If the user's task involves extracting data from a file, add a step with this tool. The `task_description` should clearly state what to extract (e.g., "Extract all tables as pandas DataFrames from the PDF").
        - If the result is a table, pass the resulting DataFrame to `analyze.analyze_data` for further analysis.

-- **duckdb_runner.retrieve_data_as_df(task: str, full_task_context: str)**:
    - **Use Case**: Use this tool ONLY if the user explicitly mentions DuckDB, SQL, or S3 in the question. Do NOT use for uploaded files unless SQL or DuckDB is specifically requested. This tool will autonomously generate and execute the necessary SQL.
    - **Input**: The `tool_input` MUST be a clear and specific STRING describing the sub-task for this step (not a dictionary or other type). The `full_task_context` is handled automatically by the agent.
    - **Returns**: A pandas DataFrame or the final answer as string.

- **fetch.extract_relevant_data(url: str, task_description: str)**:
    - **Use Case**: Use for scraping a standard webpage URL.
    - **Input**: The `tool_input` should be a JSON object with "url" and "task_description" keys.
    - **Returns**: A pandas DataFrame.

- **analyze.analyze_data(data_context: dict, task: str)**:
    - **Use Case**: This is the primary tool for all complex analysis, data cleaning, calculations, and visualizations. It takes ALL the data from previous steps and performs all the necessary transformations to answer the user's questions. It can access ALL DataFrames from previous steps to create comprehensive final results.
    - **Input**: The `tool_input` should be a very detailed string that clearly specifies:
        - What specific analysis operations need to be performed on the data (be precise about calculations, filtering, grouping, aggregations, or visualizations required)
        - The exact return format and structure expected (specify data type, format, and organization of the final result)
        - If creating a final combined result, specify how to integrate results from multiple previous steps
    - **Returns**: The final answer in the format requested by the user.
"""

    prompt = f"""
You are an Expert AI Planner. Your role is to create the most logical and efficient plan to solve the user's task by using the available tools.

**User's Task:**
---
{task_text}
---

**Uploaded Files Context:**
{file_context if file_context else 'No files uploaded.'}

**Available Tools:**
---
{tools_description}
---

**Strategy Guide:**
- **For File Upload Tasks:**
    - If the user uploads a file (CSV, Excel, PDF, image, etc.), use the `file_handler.handle_file_task` tool to extract the relevant data or content. The `task_description` should be a clear, concise instruction for what to extract (e.g., "Extract all tables as pandas DataFrames from the PDF").
    - If the file contains tables, ensure the tool returns a pandas DataFrame, which should then be passed to `analyze.analyze_data` for further analysis.
    - For text or image extraction, specify the required output format in the `task_description`.
- **For Web Scraping Tasks:**
    - Always create a two-step plan:
        1.  **`fetch` step:** Write a simple script to get the raw data. The most robust code is usually `result = pd.read_html(url)[0]`.
        2.  **`analyze` step:** Write a comprehensive script to perform ALL data cleaning, analysis, calculations, and plotting. This script should anticipate messy data (e.g., complex column names, non-numeric values) and clean it before performing the analysis.
- **For Multi-Question Tasks:**
    - If the user asks multiple questions that require different data or analysis steps, create separate steps for each data collection/processing task.
    - Always end with a final `analyze.analyze_data` step that combines ALL results from previous steps into the exact format requested by the user.
    - The final analyze step should access ALL DataFrames from previous steps and create a comprehensive response.

**CRITICAL Instructions:**
1.  **Use Provided URLs/Paths:** If the user's task includes a URL (like `https://...` or `s3://...`), you MUST use that exact URL/path in the tools you call. DO NOT invent or assume a different one.
2.  **Create a Plan:** Create a step-by-step plan using one or more of the available tools.
3.  **Output Format:** Your output MUST be a valid JSON list of dictionaries. Each dictionary must have exactly these three keys: "tool_name", "tool_input", and "step_name".
4.  **File Handler Input:** For file_handler.handle_file_task, the tool_input must be a dictionary with keys: "task_description", "full_task", and "file_path".
5.  **DuckDB Input Must Be String:** If you use the `duckdb_runner.retrieve_data_as_df` tool, the `tool_input` parameter must ALWAYS be a string, never a dictionary or other type.
6.  **Final Result:** If the user requests a specific output format (like a JSON object with multiple answers), ensure the final step creates exactly that format using ALL data from previous steps.
7.  **Default Output Format:** If no specific output format is mentioned in the user's task, the final result should be returned as a JSON array of strings, where each string is a clear, complete answer to the user's questions.

**EXAMPLE OUTPUT FORMAT:**
[
  {{
    "tool_name": "file_handler.handle_file_task",
    "tool_input": {{
      "task_description": "Extract all tables as pandas DataFrames",
      "full_task": "The full user request here",
      "file_path": "path/to/file"
    }},
    "step_name": "load_data"
  }},
  {{
    "tool_name": "analyze.analyze_data", 
    "tool_input": "Detailed analysis instructions here",
    "step_name": "analyze_results"
  }}
]

**YOUR PLAN (valid JSON only):**
"""

    # Retry loop for plan generation
    for attempt in range(3):
        try:
            logger.info(f"🤖 Plan generation attempt {attempt + 1} of 3...")
            plan_str = llm(prompt).strip()
            
            # Try to find JSON array more robustly
            # First try to find the JSON array
            match = re.search(r'\[\s*\{.*?\}\s*(?:,\s*\{.*?\}\s*)*\]', plan_str, re.DOTALL)
            if not match:
                # Try alternative pattern
                match = re.search(r'(\[[\s\S]*\])', plan_str)
            
            if not match:
                raise ValueError("LLM did not return a valid JSON list. Response: " + plan_str[:500])
            
            json_str = match.group(0)
            logger.debug(f"Extracted JSON: {json_str}")
            
            # Clean up common JSON issues
            json_str = json_str.replace('\n', ' ').replace('\r', ' ')
            # Fix common trailing comma issues
            json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
            
            plan = json.loads(json_str)
            
            # Validate plan structure
            if not isinstance(plan, list) or len(plan) == 0:
                raise ValueError("Plan must be a non-empty list")
            
            for step in plan:
                if not isinstance(step, dict):
                    raise ValueError("Each plan step must be a dictionary")
                required_keys = ["tool_name", "tool_input", "step_name"]
                for key in required_keys:
                    if key not in step:
                        raise ValueError(f"Missing required key '{key}' in plan step")
            
            logger.info(f"✅ Plan generated successfully: {plan}")
            return plan
            
        except Exception as e:
            logger.warning(f"⚠️ Plan generation attempt {attempt + 1} failed: {e}")
            if attempt == 2:  # Last attempt
                logger.error(f"❌ Failed to generate plan after 3 attempts. Last error: {e}")
                logger.error(f"Last LLM response: {plan_str[:1000] if 'plan_str' in locals() else 'No response'}")
                raise RuntimeError("The AI failed to generate a valid execution plan after 3 attempts.")
            # Continue to next attempt


def handle_task(task_text: str, attachments: dict = None, max_global_retries: int = 3) -> dict:
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
            # --- Build file context for the plan prompt ---
            file_context = ""
            import os
            import mimetypes
            import pandas as pd
            import io
            if attachments:
                for fname, fcontent in attachments.items():
                    ext = os.path.splitext(fname)[-1].lower()
                    temp_path = None
                    preview = ""
                    # Save to temp file to get a path
                    import tempfile
                    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                        tmp.write(fcontent)
                        temp_path = tmp.name
                    # Try to preview content for CSV/Excel
                    try:
                        if ext in [".csv", ".txt"]:
                            df = pd.read_csv(temp_path, nrows=5)
                            preview = f"\nPreview (first 5 rows):\n{df.head().to_markdown()}"
                        elif ext in [".xlsx", ".xls"]:
                            df = pd.read_excel(temp_path, nrows=5)
                            preview = f"\nPreview (first 5 rows):\n{df.head().to_markdown()}"
                        elif ext == ".pdf":
                            preview = "PDF file (preview not shown)"
                        elif ext in [".png", ".jpg", ".jpeg", ".gif", ".bmp"]:
                            import base64
                            with open(temp_path, "rb") as img_f:
                                img_bytes = img_f.read()
                                b64 = base64.b64encode(img_bytes).decode("utf-8")
                                mime = "image/png" if ext == ".png" else (
                                    "image/jpeg" if ext in [".jpg", ".jpeg"] else (
                                    "image/gif" if ext == ".gif" else (
                                    "image/bmp" if ext == ".bmp" else "application/octet-stream")))
                                preview = f"data:{mime};base64,{b64}"
                        else:
                            preview = "File loaded"
                    except Exception as e:
                        logger.warning(f"Preview error for {fname}: {e}")
                        preview = "File loaded (preview unavailable)"
                    
                    if temp_path:
                        tool_inputs = f"File: {fname}, Path: {temp_path}{preview}"
                        file_context += tool_inputs + "\n"
            plan = get_plan(full_task_text, file_context=file_context)

            data_context = {}
            # --- Handle file attachments: process each file and add to data_context ---
            file_temp_paths = {}  # Map logical filename to temp file path
            if attachments:
                import tempfile
                import os
                for fname, fcontent in attachments.items():
                    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(fname)[-1]) as tmp:
                        tmp.write(fcontent)
                        tmp_path = tmp.name
                    file_temp_paths[fname] = tmp_path
                    # Optionally, you can pre-load the file as a DataFrame here if you want
                    # file_result = handle_file_task(...)
                    # data_context[fname] = file_result

            for i, step in enumerate(plan):
                tool_name = step.get("tool_name")
                tool_input = step.get("tool_input")
                step_name = step.get("step_name", f"step_{i+1}")

                logger.info(f"--- Step {i+1} ({step_name}): Executing Tool: {tool_name} ---")

                step_result = None

                if tool_name == "duckdb_runner.retrieve_data_as_df":
                    if not isinstance(tool_input, str):
                        raise TypeError(f"Expected a string for duckdb_runner input, but got {type(tool_input)}")
                    step_result = retrieve_data_as_df(task=tool_input, full_task_context=full_task_text)

                elif tool_name == "fetch.extract_relevant_data":
                    if not isinstance(tool_input, dict):
                        raise TypeError(f"Expected a dictionary for fetch tool input, but got {type(tool_input)}")
                    url = tool_input.get("url")
                    task_desc = tool_input.get("task_description")
                    if not url:
                        raise ValueError("Plan for 'fetch' tool is missing a URL.")
                    step_result = extract_relevant_data(url, task_desc)

                elif tool_name == "file_handler.handle_file_task":
                    # Handle both string and dictionary inputs for backward compatibility
                    if isinstance(tool_input, str):
                        # Convert string to dictionary format
                        task_description = tool_input
                        full_task_param = full_task_text
                        # Get the first available file path
                        logical_file_path = list(file_temp_paths.keys())[0] if file_temp_paths else "uploaded_file"
                        logger.info(f"Converting string input to dictionary format for file_handler")
                    elif isinstance(tool_input, dict):
                        task_description = tool_input.get("task_description")
                        full_task_param = tool_input.get("full_task")
                        logical_file_path = tool_input.get("file_path")
                    else:
                        raise TypeError(f"Expected a dictionary or string for file_handler tool input, but got {type(tool_input)}")
                    
                    if not task_description:
                        raise ValueError("Plan for 'file_handler.handle_file_task' tool is missing task_description.")
                    
                    # Map logical file_path to actual temp file path with enhanced resolution
                    actual_file_path = file_temp_paths.get(logical_file_path)
                    
                    # Enhanced fallback strategies for file resolution
                    if not actual_file_path or not os.path.exists(actual_file_path):
                        # Strategy 1: Case-insensitive exact match
                        for k, v in file_temp_paths.items():
                            if k.lower() == logical_file_path.lower():
                                actual_file_path = v
                                logger.info(f"File resolved via case-insensitive match: {logical_file_path} -> {k}")
                                break
                        
                        # Strategy 2: Partial name matching (filename without extension)
                        if not actual_file_path:
                            logical_name = os.path.splitext(logical_file_path)[0].lower()
                            for k, v in file_temp_paths.items():
                                file_name = os.path.splitext(k)[0].lower()
                                if logical_name in file_name or file_name in logical_name:
                                    actual_file_path = v
                                    logger.info(f"File resolved via partial match: {logical_file_path} -> {k}")
                                    break
                        
                        # Strategy 3: Extension-based matching
                        if not actual_file_path:
                            logical_ext = os.path.splitext(logical_file_path)[1].lower()
                            if logical_ext:
                                matching_files = [k for k in file_temp_paths.keys() if k.lower().endswith(logical_ext)]
                                if len(matching_files) == 1:
                                    actual_file_path = file_temp_paths[matching_files[0]]
                                    logger.info(f"File resolved via extension match: {logical_file_path} -> {matching_files[0]}")
                    
                    # Strategy 4: If only one file uploaded, use it (existing fallback)
                    if (not actual_file_path or not os.path.exists(actual_file_path)) and len(file_temp_paths) == 1:
                        actual_file_path = list(file_temp_paths.values())[0]
                        logger.info(f"File resolved via single file fallback: {logical_file_path} -> {list(file_temp_paths.keys())[0]}")
                    
                    if not actual_file_path or not os.path.exists(actual_file_path):
                        available_files = list(file_temp_paths.keys())
                        raise FileNotFoundError(f"Could not resolve file '{logical_file_path}'. Available files: {available_files}. Consider using exact filenames or check file extensions.")
                    step_result = handle_file_task(
                        task_description=task_description,
                        full_task=full_task_param,
                        file_path=actual_file_path
                    )

                elif tool_name == "analyze.analyze_data":
                    logger.info(f"🤖 data_context: {data_context}")
                    step_result = analyze_data(data_context, full_task_text, tool_input=tool_input)

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
