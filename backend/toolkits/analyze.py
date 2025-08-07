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

logger = logging.getLogger(__name__)

def analyze_data(data_context: dict, task: str, max_retries: int = 3) -> list:
    """
    Takes a dictionary of DataFrames from previous steps and a task,
    and uses an LLM to generate and execute Python code to answer the questions.
    """
    logger.info("📊 Starting robust data analysis...")
    
    # --- NEW: Create a detailed preview of all dataframes in the context ---
    context_preview = ""
    for name, df in data_context.items():
        if isinstance(df, pd.DataFrame):
            context_preview += f"DataFrame `{name}` (from a previous step):\n---\n{df.head().to_markdown()}\n---\n\n"

    # --- IMPROVED PROMPT: DETAILED, YET GENERIC ---
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
1.  **Analyze the Goal:** Carefully read the `USER'S TASK` to understand what needs to be calculated and returned.
2.  **Use the Context:** Your script will have access to a dictionary named `data_context`. Access the DataFrames using their names (e.g., `data_context['get_top_court']`). **Do not use a generic `df` variable.**
3.  **Handle Data Errors:** When working with dates or numbers, write robust code. For example, use `pd.to_datetime(..., errors='coerce')` to handle invalid date formats.
4.  **Final Output:** The script must produce a final Python list containing the answers, formatted exactly as requested in the user's task. Assign this list to a variable named `result`.
5.  **Code Only:** Your entire output must be ONLY the raw Python code. Do not add explanations or markdown.

**YOUR SCRIPT:**
"""

    error_log = ""
    for attempt in range(max_retries):
        logger.info(f"Analysis attempt {attempt + 1} of {max_retries}...")

        prompt = f"{base_prompt}\n\nThe previous attempt failed with this error. Please fix the code:\n```\n{error_log}\n```" if error_log else base_prompt

        try:
            raw_analysis_code = llm(prompt)
            analysis_code = extract_python_code(raw_analysis_code)
            logger.info("✅ LLM generated analysis code. Executing...")

            # The local_vars now includes the full data_context
            local_vars = {
                "data_context": data_context,
                "pd": pd, "re": re, "plt": plt, "sns": sns,
                "io": io, "base64": base64, "json": json,
                "alt": alt, "stats": stats, "result": None
            }

            exec(analysis_code, {}, local_vars)
            final_result = local_vars.get("result")

            if isinstance(final_result, list):
                logger.info("✅ Successfully executed analysis code and got a list of results.")
                return [item.item() if hasattr(item, 'item') else item for item in final_result]
            else:
                raise ValueError(f"Analysis code did not return a list. Got type: {type(final_result)}")

        except Exception as e:
            logger.warning(f"⚠️ Analysis attempt {attempt + 1} failed: {e}")
            error_log = str(e)
            logger.debug(f"---FAILING-ANALYSIS-CODE---\n{analysis_code}\n---END-CODE---")
            if attempt + 1 == max_retries:
                logger.error("❌ All analysis attempts failed.")
                raise RuntimeError(f"Failed to analyze data after {max_retries} attempts. Last error: {e}")

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

# logger = logging.getLogger(__name__)

# def analyze_data(df: pd.DataFrame, task: str, max_retries: int = 3) -> list:
#     """
#     Takes a DataFrame and a task, and uses an LLM with a retry mechanism
#     to generate and execute Python code to answer the questions.
#     """
#     logger.info("📊 Starting robust data analysis...")
#     df_head = df.head().to_markdown()

#     base_prompt = f"""
# You are an expert Python data analyst.
# You have been given a pandas DataFrame named `df` and a task.
# Your ONLY job is to write Python code to analyze this DataFrame and answer the user's questions.

# DATAFRAME PREVIEW (`df.head()`):
# ---
# {df_head}
# ---

# TASK:
# ---
# {task}
# ---

# INSTRUCTIONS:
# 1.  **DO NOT scrape any URLs or load data from files.** You must ONLY use the provided DataFrame variable `df`.
# 2.  Write a Python script to perform the analysis described in the task.
# 3.  Your script MUST produce a final Python list of strings containing the answers.
# 4.  This final list MUST be assigned to a variable named `result`.
# 5.  **IMPORTANT: Your output must be ONLY the raw Python code. Do not include any explanations or Markdown.**
# """

#     error_log = ""
#     for attempt in range(max_retries):
#         logger.info(f"Analysis attempt {attempt + 1} of {max_retries}...")

#         if error_log:
#             prompt = f"{base_prompt}\n\nA previous attempt failed. Please fix the code. The error was:\n```\n{error_log}\n```"
#         else:
#             prompt = base_prompt

#         try:
#             raw_analysis_code = llm(prompt)
#             analysis_code = extract_python_code(raw_analysis_code)
#             logger.info("✅ LLM generated analysis code. Executing...")

#             local_vars = {
#                 "df": df.copy(), # Use a copy to avoid side effects
#                 "pd": pd, "re": re, "plt": plt, "sns": sns,
#                 "io": io, "base64": base64, "result": None
#             }

#             exec(analysis_code, {}, local_vars)
#             final_result = local_vars.get("result")

#             if isinstance(final_result, list):
#                 logger.info("✅ Successfully executed analysis code and got a list of results.")
#                 return final_result
#             else:
#                 raise ValueError(f"Analysis code did not return a list. Got type: {type(final_result)}")

#         except Exception as e:
#             logger.warning(f"⚠️ Analysis attempt {attempt + 1} failed: {e}")
#             error_log = str(e)
#             logger.debug(f"---FAILING-ANALYSIS-CODE---\n{analysis_code}\n---END-CODE---")
#             if attempt + 1 == max_retries:
#                 logger.error("❌ All analysis attempts failed.")
#                 raise RuntimeError(f"Failed to analyze data after {max_retries} attempts. Last error: {e}")

#     raise RuntimeError("Analysis failed after all retries.")
