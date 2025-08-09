# backend/toolkits/duckdb_runner.py
import duckdb
import pandas as pd
import logging
import re
import textwrap
from backend.llm_agent import llm

# Import all libraries that the generated Python script might need
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import io
import base64
import json
from scipy import stats
from sklearn.linear_model import LinearRegression
import numpy as np
import traceback

logger = logging.getLogger(__name__)

def _extract_python_code(llm_response: str) -> str:
    """Extracts Python code from an LLM response."""
    match = re.search(r'```(?:python\n)?(.*)```', llm_response, re.DOTALL)
    if match:
        return match.group(1).strip()
    return llm_response.strip()

def _generate_initial_script(task: str, full_task_context: str) -> str:
    """Asks the LLM to generate an initial Python script for data retrieval."""
    logger.info("🤖 Generating initial Python script for DuckDB task...")
    # MODIFICATION: The prompt is now focused solely on data retrieval.
    prompt = f"""
You are a Data Engineer. Your goal is to write a Python script that uses the DuckDB library to query a large dataset on S3 and return the result as a pandas DataFrame.

**Full User Task (for context, schema, and paths):**
---
{full_task_context}
---

**Specific Data Retrieval Task for this Script:**
---
{task}
---

**Instructions:**
- Write a Python script that connects to DuckDB, runs a single SQL query to fetch the data for the specific task, and returns the result as a pandas DataFrame.
- The script MUST assign the final pandas DataFrame to a variable named `result`.
- DO NOT perform any analysis, calculations, or plotting in this script.
- Return ONLY the raw Python code.

**Your Python Script:**
"""
    raw_script = llm(prompt).strip()
    return _extract_python_code(raw_script)

def _correct_python_script(failed_script: str, error_message: str, task: str, full_task_context: str) -> str:
    """Asks the LLM to correct a failed Python script based on the error message."""
    logger.info("🤖 Attempting to correct failed Python script...")
    # MODIFICATION: The correction prompt is also focused on returning a DataFrame.
    prompt = f"""
You are a Senior Python Data Scientist acting as an expert code debugger.
The following Python script failed to execute. Your task is to analyze the error and provide a corrected version.

**Original Task:**
---
{task}
---

**Full User Context:**
---
{full_task_context}
---

**Failed Script:**
```python
{failed_script}
```

**Full Error Traceback:**
```
{error_message}
```

**Instructions:**
- Carefully analyze the error traceback and the failed code.
- The corrected script's only goal is to retrieve data from DuckDB.
- The script MUST assign the final pandas DataFrame to a variable named `result`.
- Return ONLY the raw, corrected Python script.

**Corrected Script:**
"""
    raw_corrected_script = llm(prompt).strip()
    return _extract_python_code(raw_corrected_script)

# MODIFICATION: Renamed the function to reflect its specific purpose.
def retrieve_data_as_df(task: str, full_task_context: str, max_retries: int = 3) -> pd.DataFrame:
    """
    This is the main function called by the agent.
    It generates and executes a Python script to retrieve data from DuckDB,
    with a self-correction loop, and returns a pandas DataFrame.
    """
    initial_script = _generate_initial_script(task, full_task_context)
    
    current_script = textwrap.dedent(initial_script)
    for attempt in range(max_retries):
        try:
            logger.info(f"Python script attempt {attempt + 1} of {max_retries}...")
            logger.info(f"Executing Python Script:\n---START-SCRIPT---\n{current_script}\n---END-SCRIPT---")

            local_vars = {
                "duckdb": duckdb, "pd": pd, "re": re,
                "result": None
            }

            exec(current_script, local_vars)
            final_result = local_vars.get("result")

            # MODIFICATION: The tool now strictly expects a pandas DataFrame as the result.
            if isinstance(final_result, pd.DataFrame):
                logger.info("✅ Script executed successfully and returned a DataFrame.")
                return final_result
            else:
                raise ValueError(f"Script did not return a pandas DataFrame. Got type: {type(final_result)}")

        except Exception as e:
            error_log = traceback.format_exc()
            logger.warning(f"⚠️ Script failed on attempt {attempt + 1}:\n{error_log}")
            
            if attempt + 1 == max_retries:
                logger.error("❌ All script execution attempts failed.")
                raise RuntimeError(f"Script failed after {max_retries} attempts. Last error: {e}")
            
            current_script = _correct_python_script(current_script, error_log, task, full_task_context)
    
    raise RuntimeError("DuckDB tool failed to execute after all retries.")







# # backend/toolkits/duckdb_runner.py
# import duckdb
# import pandas as pd
# import logging
# import re
# from backend.llm_agent import llm

# logger = logging.getLogger(__name__)

# def _extract_sql_code(llm_response: str) -> str:
#     """Extracts SQL code from an LLM response that might be wrapped in Markdown."""
#     match = re.search(r'```(?:sql\n)?(.*)```', llm_response, re.DOTALL)
#     if match:
#         return match.group(1).strip()
#     return llm_response.strip()

# def _generate_initial_query(task: str, full_task_context: str) -> str:
#     """Asks the LLM to generate an initial DuckDB query based on the task."""
#     logger.info("🤖 Generating initial DuckDB query...")
#     prompt = f"""
# You are a DuckDB expert. Based on the user's task, write a single, complete DuckDB SQL query to retrieve the necessary data.

# **Full User Task (for context, schema, and paths):**
# ---
# {full_task_context}
# ---

# **Specific Sub-Task for this Query:**
# ---
# {task}
# ---

# **DuckDB Best Practices:**
# - **For linear regression:** Use the built-in `regr_slope(Y, X)` function. Do NOT calculate slope manually.
# - **For date differences:** Use `DATE_DIFF('day', start_date, end_date)` to get the difference in days.
# - **For date parsing:** Use `STRPTIME(date_string, '%d-%m-%Y')` to convert string dates.
# - **Casting:** Ensure you cast columns to the correct types (e.g., `::DOUBLE`, `::DATE`) before using them in functions.

# **Instructions:**
# - Use the S3 path and schema information from the "Full User Task" to construct your query.
# - The query must include all necessary `INSTALL` and `LOAD` commands for httpfs and parquet.
# - Return ONLY the raw SQL query.

# **Your Query:**
# """
#     raw_query = llm(prompt).strip()
#     return _extract_sql_code(raw_query)

# def _correct_duckdb_query(failed_query: str, error_message: str, task: str, full_task_context: str) -> str:
#     """Asks the LLM to correct a failed DuckDB query based on the error message."""
#     logger.info("🤖 Attempting to correct failed DuckDB query...")
#     prompt = f"""
# You are a DuckDB expert. The following query failed to execute.
# Your task is to correct the query based on the error message and the full task context.

# **Full User Task (for context, schema, and paths):**
# ---
# {full_task_context}
# ---

# **Specific Sub-Task for this Query:**
# ---
# {task}
# ---

# **Failed Query:**
# ```sql
# {failed_query}
# ```

# **Error Message:**
# ```
# {error_message}
# ```

# **Instructions:**
# - Analyze the error and the original query.
# - Use the S3 path and schema from the "Full User Task" to fix the query.
# - Return ONLY the raw, corrected SQL query.

# **Corrected Query:**
# """
#     raw_corrected_query = llm(prompt).strip()
#     return _extract_sql_code(raw_corrected_query)

# def generate_and_run_query(task: str, full_task_context: str, max_retries: int = 3) -> pd.DataFrame:
#     """
#     This is the main function called by the agent.
#     It generates and executes a DuckDB query based on a task, with a self-correction loop.
#     """
#     initial_query = _generate_initial_query(task, full_task_context)
    
#     current_query = initial_query
#     for attempt in range(max_retries):
#         try:
#             logger.info(f"DuckDB attempt {attempt + 1} of {max_retries}...")
#             logger.info(f"Executing DuckDB Query:\n---START-QUERY---\n{current_query}\n---END-QUERY---")

#             con = duckdb.connect(database=':memory:', read_only=False)
            
#             result_df = con.sql(current_query).df()
            
#             logger.info(f"✅ Query successful on attempt {attempt + 1}. Returned DataFrame with shape: {result_df.shape}")
#             return result_df

#         except Exception as e:
#             logger.warning(f"⚠️ DuckDB query failed on attempt {attempt + 1}: {e}")
#             error_message = str(e)
#             if attempt + 1 == max_retries:
#                 logger.error("❌ All DuckDB attempts failed.")
#                 raise RuntimeError(f"DuckDB query failed after {max_retries} attempts. Last error: {error_message}")
            
#             current_query = _correct_duckdb_query(current_query, error_message, task, full_task_context)
    
#     raise RuntimeError("DuckDB tool failed to execute after all retries.")
