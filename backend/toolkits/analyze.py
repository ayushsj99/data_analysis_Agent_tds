# backend/toolkits/analyze.py

import pandas as pd
import logging
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


def analyze_data(data_context: dict, task: str, max_retries: int = 3) -> list:
    """
    Takes a dictionary of DataFrames from previous steps and a task,
    and uses an LLM to generate and execute Python code to answer the questions.
    """
    logger.info("📊 Starting robust data analysis...")
    
    context_preview = ""
    for name, df in data_context.items():
        if isinstance(df, pd.DataFrame):
            buffer = io.StringIO()
            df.info(buf=buffer)
            df_info = buffer.getvalue()
            
            context_preview += f"DataFrame `{name}`:\n"
            context_preview += f"--- Head ---\n{df.head().to_markdown()}\n"
            context_preview += f"--- Tail ---\n{df.tail().to_markdown()}\n"
            context_preview += f"--- Info ---\n{df_info}\n---\n\n"
    
    logger.info(f"Data Context Preview:\n{context_preview}")

    base_prompt = f"""
You are a Senior Python Data Scientist. Your goal is to write a Python script to complete a user's task.
You have been provided with a `data_context` dictionary containing one or more pandas DataFrames from previous steps.

**DATA CONTEXT:**
---
{context_preview}
---

**USER'S TASK:**
---
{task}
---

**INSTRUCTIONS:**
1.  **Analyze the Data Context:** Carefully examine the `head`, `tail`, and `info` for each DataFrame to understand its structure.
2.  **Write a Python Script:** Create a single, top-level Python script to perform all the necessary cleaning, analysis, and visualization.
3.  **Access Data Correctly:** Your script must access the DataFrames from the `data_context` dictionary (e.g., `data_context['scrape_data']`).
4.  **Final Output:** The script must assign the final answer to a variable named `result`. The format of the `result` must match the user's task.
5.  **Code Only:** Your entire output must be ONLY the raw Python code.

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
                if hasattr(final_result, 'item'):
                    return final_result.item()
                if isinstance(final_result, dict):
                    return {k: (v.item() if hasattr(v, 'item') else v) for k, v in final_result.items()}
                if isinstance(final_result, list):
                    return [item.item() if hasattr(item, 'item') else item for item in final_result]
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


# # backend/toolkits/analyze.py

# import pandas as pd
# import logging
# from backend.llm_agent import llm
# from .fetch import extract_python_code # Reuse the code extractor

# # We need to import all libraries that the LLM might use in its code
# import re
# import matplotlib
# matplotlib.use('Agg') # Use a non-interactive backend for plotting
# import matplotlib.pyplot as plt
# import seaborn as sns
# import io
# import base64
# import json
# import altair as alt
# from scipy import stats

# logger = logging.getLogger(__name__)

# def analyze_data(data_context: dict, task: str, max_retries: int = 3) -> list:
#     """
#     Takes a dictionary of DataFrames from previous steps and a task,
#     and uses an LLM to generate and execute Python code to answer the questions.
#     """
#     logger.info("📊 Starting robust data analysis...")
    
#     # --- Create a detailed preview of all dataframes in the context ---
#     context_preview = ""
#     for name, df in data_context.items():
#         if isinstance(df, pd.DataFrame):
#             # Use an in-memory buffer to capture the output of df.info()
#             buffer = io.StringIO()
#             df.info(buf=buffer)
#             df_info = buffer.getvalue()
            
#             context_preview += f"DataFrame `{name}`:\n"
#             context_preview += f"--- Head ---\n{df.head().to_markdown()}\n"
#             # --- THIS IS THE FIX: Add the tail of the DataFrame ---
#             context_preview += f"--- Tail ---\n{df.tail().to_markdown()}\n"
#             context_preview += f"--- Info ---\n{df_info}\n---\n\n"
    
#     logger.info(f"Data Context Preview:\n{context_preview}")

#     # --- IMPROVED PROMPT: DETAILED, YET GENERIC ---
#     base_prompt = f"""
# You are a Senior Python Data Scientist. Your goal is to write a Python script to complete a user's task.
# You have been provided with a `data_context` dictionary containing one or more pandas DataFrames from previous steps.

# **DATA CONTEXT:**
# ---
# {context_preview}
# ---

# **USER'S TASK:**
# ---
# {task}
# ---

# **INSTRUCTIONS:**
# 1.  **Analyze the Data Context:** Carefully examine the `head`, `tail`, and `info` for each DataFrame to understand its structure, column names, and data types. This is critical for writing correct code.
# 2.  **Write a Python Script:** Create a single, top-level Python script to perform all the necessary cleaning, analysis, and visualization.
# 3.  **Access Data Correctly:** Your script must access the DataFrames from the `data_context` dictionary using their names (e.g., `data_context['scrape_data']`).
# 4.  **Final Output:** The script must assign the final answer to a variable named `result`. The format of the `result` must match what the user's task requested (e.g., a JSON array of strings, a dictionary).
# 5.  **Code Only:** Your entire output must be ONLY the raw Python code. Do not add explanations or markdown.

# **YOUR SCRIPT:**
# """

#     error_log = ""
#     for attempt in range(max_retries):
#         logger.info(f"Analysis attempt {attempt + 1} of {max_retries}...")

#         prompt = f"{base_prompt}\n\nThe previous attempt failed with this error. Please fix the code:\n```\n{error_log}\n```" if error_log else base_prompt

#         try:
#             raw_analysis_code = llm(prompt)
#             analysis_code = extract_python_code(raw_analysis_code)
#             logger.info("✅ LLM generated analysis code. Executing...")
            
#             logger.info(f"Executing Analysis Code:\n---START-CODE---\n{analysis_code}\n---END-CODE---")

#             local_vars = {
#                 "data_context": data_context,
#                 "pd": pd, "re": re, "plt": plt, "sns": sns,
#                 "io": io, "base64": base64, "json": json,
#                 "alt": alt, "stats": stats, "result": None
#             }

#             exec(analysis_code, local_vars)
#             final_result = local_vars.get("result")

#             # --- Ensure all images are returned as base64 data URIs ---
#             def to_base64_image(val):
#                 import base64
#                 import io
#                 if hasattr(val, 'save') and callable(val.save):
#                     # It's a PIL Image
#                     buf = io.BytesIO()
#                     val.save(buf, format='PNG')
#                     b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
#                     return f"data:image/png;base64,{b64}"
#                 if isinstance(val, (bytes, bytearray)):
#                     b64 = base64.b64encode(val).decode('utf-8')
#                     return f"data:image/png;base64,{b64}"
#                 return val

#             if isinstance(final_result, dict):
#                 for k, v in final_result.items():
#                     if hasattr(v, 'save') or isinstance(v, (bytes, bytearray)):
#                         final_result[k] = to_base64_image(v)
#             elif hasattr(final_result, 'save') or isinstance(final_result, (bytes, bytearray)):
#                 final_result = to_base64_image(final_result)

#             if final_result is not None:
#                 logger.info("✅ Successfully executed analysis code.")
#                 if hasattr(final_result, 'item'):
#                     return final_result.item()
#                 if isinstance(final_result, dict):
#                     return {k: (v.item() if hasattr(v, 'item') else v) for k, v in final_result.items()}
#                 if isinstance(final_result, list):
#                     return [item.item() if hasattr(item, 'item') else item for item in final_result]
#                 return final_result
#             else:
#                 raise ValueError("Analysis code did not assign a value to the 'result' variable.")

#         except Exception as e:
#             logger.warning(f"⚠️ Analysis attempt {attempt + 1} failed: {e}")
#             error_log = str(e)
#             logger.debug(f"---FAILING-ANALYSIS-CODE---\n{analysis_code}\n---END-CODE---")
#             if attempt + 1 == max_retries:
#                 logger.error("❌ All analysis attempts failed.")
#                 raise RuntimeError(f"Failed to analyze data after {max_retries} attempts. Last error: {e}")

#     raise RuntimeError("Analysis failed after all retries.")
