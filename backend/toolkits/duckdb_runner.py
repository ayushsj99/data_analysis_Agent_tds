# backend/toolkits/duckdb_runner.py
import duckdb
import pandas as pd
import logging
import re
import textwrap
from backend.llm_agent import llm

logger = logging.getLogger(__name__)

def _extract_sql_code(llm_response: str) -> str:
    """Extracts SQL code from an LLM response that might be wrapped in Markdown."""
    match = re.search(r'```(?:sql\n)?(.*)```', llm_response, re.DOTALL)
    if match:
        return match.group(1).strip()
    return llm_response.strip()

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
- Return ONLY the raw, corrected SQL query.

**Corrected Query:**
"""
    raw_corrected_query = llm(prompt).strip()
    return _extract_sql_code(raw_corrected_query)

def execute_query(code: str, task: str, execution_log: list, max_retries: int = 3) -> pd.DataFrame:
    """
    Executes pre-written DuckDB code with a self-correction loop and logs corrections.
    """
    current_query = textwrap.dedent(_extract_sql_code(code))
    
    for attempt in range(max_retries):
        try:
            logger.info(f"DuckDB attempt {attempt + 1} of {max_retries}...")
            # --- NEW: Log the code before execution ---
            logger.info(f"Executing DuckDB Code:\n---START-CODE---\n{current_query}\n---END-CODE---")
            
            con = duckdb.connect(database=':memory:', read_only=False)
            
            result_df = con.sql(current_query).df()
            
            logger.info(f"✅ Query successful on attempt {attempt + 1}. Returned DataFrame with shape: {result_df.shape}")
            return result_df

        except Exception as e:
            logger.warning(f"⚠️ DuckDB query failed on attempt {attempt + 1}: {e}")
            error_message = str(e)
            if attempt + 1 == max_retries:
                logger.error("❌ All DuckDB attempts failed.")
                raise RuntimeError(f"DuckDB query failed after {max_retries} attempts. Last error: {error_message}")
            
            corrected_query_raw = _correct_duckdb_query(current_query, error_message, task)
            log_entry = f"--- Corrected DuckDB Query (Attempt {attempt + 2}) ---\n{corrected_query_raw}"
            execution_log.append(log_entry)
            
            current_query = textwrap.dedent(corrected_query_raw)
    
    raise RuntimeError("DuckDB tool failed to execute after all retries.")
