# backend/toolkits/analyze.py

import pandas as pd
import logging
import io
import gc  # For garbage collection in memory optimization
from backend.llm_agent import llm
from .fetch import extract_python_code # Reuse the code extractor

# We need to import all libraries that the LLM might use in its code
import re
import matplotlib
matplotlib.use('Agg') # Use a non-interactive backend for plotting
import matplotlib.pyplot as plt
import seaborn as sns
import io
import base64
import json
import altair as alt
from scipy import stats
import traceback # <-- Import the traceback module

logger = logging.getLogger(__name__)

def _correct_analysis_code(failed_code: str, error_message: str, task: str, data_context_preview: str) -> str:
    """
    This function acts as an expert debugger. It asks the LLM to correct 
    failed Python analysis code based on a rich context.
    """
    logger.info("🤖 Attempting to correct failed analysis code...")
    prompt = f"""
You are a Senior Python Data Scientist acting as an expert code debugger.
The following Python script failed to execute. Your task is to analyze the error traceback
and provide a corrected version of the script.

**Original Task:**
---
{task}
---

**Data Context Preview (the script has access to a `data_context` dictionary):**
---
{data_context_preview}
---

**Failed Code:**
```python
{failed_code}
```

**Full Error Traceback:**
```
{error_message}
```

**Instructions:**
- Carefully analyze the error traceback, the failed code, and the available data context.
- The corrected script must successfully complete the original task.
- The script must assign the final answer to a variable named `result`.
- Return ONLY the raw, corrected Python script.

**Corrected Code:**
"""
    raw_corrected_code = llm(prompt).strip()
    return extract_python_code(raw_corrected_code)


def analyze_data(data_context: dict, task: str, max_retries: int = 3, tool_input: dict = None) -> list:
    """
    Takes a dictionary of DataFrames from previous steps and a task,
    and uses an LLM to generate and execute Python code to answer the questions.
    """
    logger.info("📊 Starting robust data analysis...")
    
    # Memory management: Check data context size
    total_memory_mb = 0
    large_datasets = []
    
    for name, data in data_context.items():
        if isinstance(data, pd.DataFrame):
            df_memory = data.memory_usage(deep=True).sum() / (1024 * 1024)  # MB
            total_memory_mb += df_memory
            if df_memory > 50:  # 50MB threshold
                large_datasets.append((name, df_memory, data.shape))
        elif isinstance(data, dict):
            for sub_name, sub_df in data.items():
                if isinstance(sub_df, pd.DataFrame):
                    df_memory = sub_df.memory_usage(deep=True).sum() / (1024 * 1024)
                    total_memory_mb += df_memory
                    if df_memory > 50:
                        large_datasets.append((f"{name}['{sub_name}']", df_memory, sub_df.shape))
    
    if large_datasets:
        logger.warning(f"Large datasets detected (Total: {total_memory_mb:.1f}MB): {large_datasets}")
    
    context_preview = ""
    for name, data in data_context.items():
        if isinstance(data, pd.DataFrame):
            # Direct DataFrame with memory optimization
            df_memory = data.memory_usage(deep=True).sum() / (1024 * 1024)
            buffer = io.StringIO()
            data.info(buf=buffer)
            df_info = buffer.getvalue()
            
            # Optimize preview for large DataFrames
            preview_rows = 3 if df_memory > 100 else 5  # Fewer rows for very large datasets
            
            context_preview += f"DataFrame `{name}` (Memory: {df_memory:.1f}MB):\n"
            context_preview += f"--- Head ({preview_rows} rows) ---\n{data.head(preview_rows).to_markdown()}\n"
            context_preview += f"--- Tail ({preview_rows} rows) ---\n{data.tail(preview_rows).to_markdown()}\n"
            context_preview += f"--- Info ---\n{df_info}\n---\n\n"
        
        elif isinstance(data, dict):
            # Dictionary of DataFrames (e.g., Excel sheets, multiple tables)
            context_preview += f"Collection `{name}` (dictionary with {len(data)} items):\n"
            for sub_name, sub_df in data.items():
                if isinstance(sub_df, pd.DataFrame):
                    df_memory = sub_df.memory_usage(deep=True).sum() / (1024 * 1024)
                    buffer = io.StringIO()
                    sub_df.info(buf=buffer)
                    df_info = buffer.getvalue()
                    
                    preview_rows = 3 if df_memory > 50 else 5
                    
                    context_preview += f"  DataFrame `{name}['{sub_name}']` (Memory: {df_memory:.1f}MB):\n"
                    context_preview += f"  --- Head ({preview_rows} rows) ---\n{sub_df.head(preview_rows).to_markdown()}\n"
                    context_preview += f"  --- Tail ({preview_rows} rows) ---\n{sub_df.tail(preview_rows).to_markdown()}\n"
                    context_preview += f"  --- Info ---\n{df_info}\n"
                else:
                    context_preview += f"  `{name}['{sub_name}']`: {type(sub_df)} (not a DataFrame)\n"
            context_preview += "---\n\n"
        
        else:
            # Other data types
            context_preview += f"`{name}`: {type(data)} (not a DataFrame or dictionary)\n---\n\n"
    
    logger.info(f"Data Context Preview:\n{context_preview}")

    tool_input_str = json.dumps(tool_input, indent=2) if tool_input else "{}"
    base_prompt = f"""
You are a Senior Python Data Scientist. Your goal is to write a Python script to complete the MAIN TASK described in the TOOL INPUT below.
You have been provided with:
- a `data_context` dictionary containing one or more pandas DataFrames from previous steps,
- a `tool_input` dictionary which contains the MAIN TASK and any parameters for this analysis step,
- a `task` string which is ONLY for context and background (not for file names or resources).

**DATA CONTEXT PREVIEW:**
---
{context_preview}
---

**CONTEXT (for background only, do NOT use file names/resources from here):**
---
{task}
---

**MAIN TASK (TOOL INPUT):**
---
{tool_input_str}
---

**STRICT INSTRUCTIONS:**
1.  The MAIN TASK is defined by the TOOL INPUT. Use this as the sole source for what code to generate.
2.  The CONTEXT is for background only. Do NOT use any file names, file paths, or resources mentioned in the CONTEXT. Do NOT attempt to read or reference files from the CONTEXT. Only use the DataFrames and names shown in the DATA CONTEXT PREVIEW.
3.  Use the DATA CONTEXT PREVIEW to determine the names, structure, and content of the DataFrames available for analysis. You have access to ALL DataFrames from ALL previous steps - use whichever ones are needed to complete the MAIN TASK.
4.  **DATA ACCESS PATTERNS:**
   - For direct DataFrames: `data_context['step_name']` 
   - For dictionary collections: `data_context['step_name']['sheet_name']` or `data_context['step_name']['table_name']`
   - Check the DATA CONTEXT PREVIEW above to see the exact access pattern for each dataset
5.  If the MAIN TASK requires combining results from multiple DataFrames or previous steps, access and use ALL relevant DataFrames from the `data_context` dictionary.
6.  Write a single, top-level Python script to perform all necessary cleaning, analysis, and visualization as required by the MAIN TASK.
7.  **MEMORY OPTIMIZATION**: For large datasets (>50MB), use efficient operations like sampling, chunking, or vectorized operations. Avoid operations that duplicate large DataFrames unnecessarily.
8.  The script must assign the final answer to a variable named `result`. The format of the `result` must match the MAIN TASK exactly.
9.  **Default Output Format:** If the MAIN TASK does not specify a particular output format, return the result as a JSON array of strings (Python list of strings), where each string contains a clear, complete answer.
10. Your entire output must be ONLY the raw Python code. Do not add explanations or markdown.

**YOUR SCRIPT:**
"""

    # Generate the initial code once, outside the loop
    logger.info("🤖 Generating initial analysis code...")
    raw_analysis_code = llm(base_prompt)
    analysis_code = extract_python_code(raw_analysis_code)

    for attempt in range(max_retries):
        logger.info(f"Analysis attempt {attempt + 1} of {max_retries}...")

        try:
            logger.info(f"Executing Analysis Code:\n---START-CODE---\n{analysis_code}\n---END-CODE---")

            local_vars = {
                "data_context": data_context,
                "pd": pd, "re": re, "plt": plt, "sns": sns,
                "io": io, "base64": base64, "json": json,
                "alt": alt, "stats": stats, "result": None
            }

            exec(analysis_code, local_vars)
            final_result = local_vars.get("result")

            # --- Ensure all images are returned as base64 data URIs ---
            def to_base64_image(val):
                import base64
                import io
                if hasattr(val, 'save') and callable(val.save):
                    # It's a PIL Image
                    buf = io.BytesIO()
                    val.save(buf, format='PNG')
                    b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
                    return f"data:image/png;base64,{b64}"
                if isinstance(val, (bytes, bytearray)):
                    b64 = base64.b64encode(val).decode('utf-8')
                    return f"data:image/png;base64,{b64}"
                return val

            if isinstance(final_result, dict):
                for k, v in final_result.items():
                    if hasattr(v, 'save') or isinstance(v, (bytes, bytearray)):
                        final_result[k] = to_base64_image(v)
            elif hasattr(final_result, 'save') or isinstance(final_result, (bytes, bytearray)):
                final_result = to_base64_image(final_result)

            if final_result is not None:
                logger.info("✅ Successfully executed analysis code.")
                
                # Log result summary without full base64 content to avoid truncation
                if isinstance(final_result, dict):
                    result_summary = {}
                    for k, v in final_result.items():
                        if isinstance(v, str) and len(v) > 1000:
                            # Truncate long strings (likely base64 images)
                            result_summary[k] = f"<large_content_{len(v)}_chars>"
                        elif isinstance(v, list) and len(v) > 10:
                            result_summary[k] = f"<list_with_{len(v)}_items>"
                        else:
                            result_summary[k] = v
                    logger.info(f"Final Result Summary:\n{result_summary}")
                else:
                    if isinstance(final_result, str) and len(final_result) > 1000:
                        logger.info(f"Final Result: <large_content_{len(final_result)}_chars>")
                    else:
                        logger.info(f"Final Result:\n{final_result}")
                        
                if hasattr(final_result, 'item'):
                    return final_result.item()
                if isinstance(final_result, dict):
                    return {k: (v.item() if hasattr(v, 'item') else v) for k, v in final_result.items()}
                if isinstance(final_result, list):
                    return [item.item() if hasattr(item, 'item') else item for item in final_result]
                
                # Memory cleanup for large datasets
                if total_memory_mb > 100:
                    gc.collect()
                    logger.info(f"Memory cleanup performed after processing {total_memory_mb:.1f}MB of data")
                
                return final_result
            else:
                raise ValueError("Analysis code did not assign a value to the 'result' variable.")

        except Exception as e:
            # --- THE FIX: Capture the full traceback for better debugging context ---
            error_log = traceback.format_exc()
            logger.warning(f"⚠️ Analysis attempt {attempt + 1} failed:\n{error_log}")
            
            logger.debug(f"---FAILING-ANALYSIS-CODE---\n{analysis_code}\n---END-CODE---")
            if attempt + 1 == max_retries:
                logger.error("❌ All analysis attempts failed.")
                # Pass the original exception 'e' for a cleaner final error message to the user
                raise RuntimeError(f"Failed to analyze data after {max_retries} attempts. Last error: {e}")
            
            # On failure, call the expert debugger to get corrected code for the next attempt
            analysis_code = _correct_analysis_code(analysis_code, error_log, task, context_preview)

    raise RuntimeError("Analysis failed after all retries.")


