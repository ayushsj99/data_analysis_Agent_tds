# backend/toolkits/duckdb_runner.py
import duckdb
import pandas as pd
import logging
import re # <-- Add this import
from backend.llm_agent import llm

logger = logging.getLogger(__name__)

def _extract_sql_code(llm_response: str) -> str:
    """
    Extracts SQL code from an LLM response that might be wrapped
    in Markdown code blocks (```sql ... ```).
    """
    match = re.search(r'```(?:sql\n)?(.*)```', llm_response, re.DOTALL)
    if match:
        # If a markdown block is found, return its content
        logger.info("✅ Extracted SQL from Markdown block.")
        return match.group(1).strip()
    else:
        # If no markdown block, assume the whole response is code
        logger.warning("⚠️ No Markdown block found. Assuming entire response is SQL.")
        return llm_response.strip()

def _generate_initial_query(task: str) -> str:
    """Asks the LLM to generate an initial DuckDB query based on the task."""
    logger.info("🤖 Generating initial DuckDB query...")
    prompt = f"""
You are a DuckDB expert. Based on the user's task, write a single, complete DuckDB SQL query to retrieve the necessary data.

**User's Task:**
{task}

**Instructions:**
- The query must include all necessary `INSTALL` and `LOAD` commands for httpfs and parquet.
- Return ONLY the raw SQL query.

**Your Query:**
"""
    raw_query = llm(prompt).strip()
    # --- THIS IS THE FIX ---
    # Clean the query before returning it
    return _extract_sql_code(raw_query)

def _correct_duckdb_query(failed_query: str, error_message: str, task: str) -> str:
    """Asks the LLM to correct a failed DuckDB query based on the error message."""
    logger.info("🤖 Attempting to correct failed DuckDB query...")
    prompt = f"""
You are a DuckDB expert. The following query failed to execute.
Your task is to correct the query based on the error message.

**Original Task:**
{task}

**Failed Query:**
```sql
{failed_query}
```

**Error Message:**
```
{error_message}
```

**Instructions:**
- Analyze the error and the original query.
- Return ONLY the raw, corrected SQL query. Do not add explanations or markdown.

**Corrected Query:**
"""
    raw_corrected_query = llm(prompt).strip()
    # --- THIS IS THE FIX ---
    # Clean the corrected query before returning it
    return _extract_sql_code(raw_corrected_query)

def generate_and_run_query(task: str, max_retries: int = 3) -> pd.DataFrame:
    """
    This is the main function called by the agent.
    It generates and executes a DuckDB query based on a task, with a self-correction loop.
    """
    initial_query = _generate_initial_query(task)
    
    current_query = initial_query
    for attempt in range(max_retries):
        try:
            logger.info(f"DuckDB attempt {attempt + 1} of {max_retries}...")
            con = duckdb.connect(database=':memory:', read_only=False)
            
            # The query is now clean and should not contain INSTALL/LOAD commands
            # unless absolutely necessary, as they are handled here.
            con.execute("INSTALL httpfs; LOAD httpfs;")
            con.execute("INSTALL parquet; LOAD parquet;")
            
            result_df = con.sql(current_query).df()
            
            logger.info(f"✅ Query successful on attempt {attempt + 1}. Returned DataFrame with shape: {result_df.shape}")
            return result_df

        except Exception as e:
            logger.warning(f"⚠️ DuckDB query failed on attempt {attempt + 1}: {e}")
            error_message = str(e)
            if attempt + 1 == max_retries:
                logger.error("❌ All DuckDB attempts failed.")
                raise RuntimeError(f"DuckDB query failed after {max_retries} attempts. Last error: {error_message}")
            
            current_query = _correct_duckdb_query(current_query, error_message, task)
    
    raise RuntimeError("DuckDB tool failed to execute after all retries.")
