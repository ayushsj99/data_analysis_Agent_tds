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

logger = logging.getLogger(__name__)

def analyze_data(df: pd.DataFrame, task: str, max_retries: int = 3) -> list:
    """
    Takes a DataFrame and a task, and uses an LLM with a retry mechanism
    to generate and execute Python code to answer the questions.
    """
    logger.info("📊 Starting robust data analysis...")
    df_head = df.head().to_markdown()

    base_prompt = f"""
You are an expert Python data analyst.
You have been given a pandas DataFrame named `df` and a task.
Your ONLY job is to write Python code to analyze this DataFrame and answer the user's questions.

DATAFRAME PREVIEW (`df.head()`):
---
{df_head}
---

TASK:
---
{task}
---

INSTRUCTIONS:
1.  **DO NOT scrape any URLs or load data from files.** You must ONLY use the provided DataFrame variable `df`.
2.  Write a Python script to perform the analysis described in the task.
3.  Your script MUST produce a final Python list of strings containing the answers.
4.  This final list MUST be assigned to a variable named `result`.
5.  **IMPORTANT: Your output must be ONLY the raw Python code. Do not include any explanations or Markdown.**
"""

    error_log = ""
    for attempt in range(max_retries):
        logger.info(f"Analysis attempt {attempt + 1} of {max_retries}...")

        if error_log:
            prompt = f"{base_prompt}\n\nA previous attempt failed. Please fix the code. The error was:\n```\n{error_log}\n```"
        else:
            prompt = base_prompt

        try:
            raw_analysis_code = llm(prompt)
            analysis_code = extract_python_code(raw_analysis_code)
            logger.info("✅ LLM generated analysis code. Executing...")

            local_vars = {
                "df": df.copy(), # Use a copy to avoid side effects
                "pd": pd, "re": re, "plt": plt, "sns": sns,
                "io": io, "base64": base64, "result": None
            }

            exec(analysis_code, {}, local_vars)
            final_result = local_vars.get("result")

            if isinstance(final_result, list):
                logger.info("✅ Successfully executed analysis code and got a list of results.")
                return final_result
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
