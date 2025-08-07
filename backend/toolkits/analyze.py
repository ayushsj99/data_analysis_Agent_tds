# backend/toolkits/analyze.py

import pandas as pd
import logging
import re
import textwrap
from backend.llm_agent import llm
from .fetch import _extract_python_code

# Import all libraries that the LLM might use
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import io
import base64
import json
import altair as alt
from scipy import stats

logger = logging.getLogger(__name__)

def _correct_analysis_code(failed_code: str, error_message: str, task: str, data_context_preview: str) -> str:
    """Asks the LLM to correct failed Python analysis code."""
    logger.info("🤖 Attempting to correct failed analysis code...")
    prompt = f"""
You are a Senior Python Data Scientist. The following Python script failed.
Your task is to correct the script based on the error message and the data context.

**Original Task:**
{task}

**Data Context Preview:**
{data_context_preview}

**Failed Code:**
```python
{failed_code}
```

**Error Message:**
```
{error_message}
```
**Execution Environment:**
- The Python code for this tool is executed using Python's `exec()` function.
- The code will have access to pre-defined variables in its local scope, including `pd` (pandas), `plt` (matplotlib), `sns` (seaborn), and `data_context` (a dictionary of results from previous steps).
- **CRITICAL:** Because of this, the code you write must be a simple, top-level script. **DO NOT wrap your code in a function definition (e.g., `def my_function(): ...`)**.
**Instructions:**
- Analyze the error, the code, and the data context.
- The corrected script must assign the final answer to a variable named `result`.
- Return ONLY the raw, corrected Python script.

**Corrected Code:**
"""
    raw_corrected_code = llm(prompt).strip()
    return _extract_python_code(raw_corrected_code)

def execute_analysis(code: str, data_context: dict, task: str, execution_log: list, max_retries: int = 3) -> any:
    """
    Executes pre-written Python analysis code with a self-correction loop and logs corrections.
    """
    current_code = textwrap.dedent(_extract_python_code(code))

    context_preview = ""
    for name, data in data_context.items():
        if isinstance(data, pd.DataFrame):
            context_preview += f"DataFrame `{name}`:\n---\n{data.head().to_markdown()}\n---\n\n"

    for attempt in range(max_retries):
        try:
            logger.info(f"Analysis attempt {attempt + 1} of {max_retries}...")
            # --- NEW: Log the code before execution ---
            logger.info(f"Executing Analysis Code:\n---START-CODE---\n{current_code}\n---END-CODE---")
            
            local_vars = {
                "data_context": data_context,
                "pd": pd, "re": re, "plt": plt, "sns": sns, "io": io,
                "base64": base64, "json": json, "alt": alt, "stats": stats,
                "result": None
            }

            exec(current_code, {}, local_vars)
            final_result = local_vars.get("result")

            if final_result is not None:
                logger.info("✅ Analysis successful on attempt %d.", attempt + 1)
                
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
            logger.warning(f"⚠️ Analysis attempt {attempt + 1} failed: {e}")
            error_message = str(e)
            if attempt + 1 == max_retries:
                logger.error("❌ All analysis attempts failed.")
                raise RuntimeError(f"Analysis failed after {max_retries} attempts. Last error: {error_message}")
            
            corrected_code_raw = _correct_analysis_code(current_code, error_message, task, context_preview)
            log_entry = f"--- Corrected Analysis Code (Attempt {attempt + 2}) ---\n{corrected_code_raw}"
            execution_log.append(log_entry)
            
            current_code = textwrap.dedent(corrected_code_raw)
    
    raise RuntimeError("Analysis tool failed to execute after all retries.")
