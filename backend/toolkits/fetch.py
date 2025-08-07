# backend/toolkits/fetch.py

import pandas as pd
import requests
from bs4 import BeautifulSoup
from backend.llm_agent import llm
import re
import logging
import textwrap

logger = logging.getLogger(__name__)

def _extract_python_code(llm_response: str) -> str:
    """Extracts Python code from an LLM response."""
    match = re.search(r'```(?:python\n)?(.*)```', llm_response, re.DOTALL)
    if match:
        return match.group(1).strip()
    return llm_response.strip()

def _correct_fetch_code(failed_code: str, error_message: str, task: str, html_snippet: str) -> str:
    """Asks the LLM to correct failed Python scraping code."""
    logger.info("🤖 Attempting to correct failed scraping code...")
    prompt = f"""
You are a Senior Python Web Scraping expert. The following Python script failed to execute.
Your task is to correct the script based on the error message and the provided HTML context.

**Original Task:**
{task}

**HTML Snippet:**
```html
{html_snippet}
```

**Failed Code:**
```python
{failed_code}
```

**Error Message:**
```
{error_message}
```

**Instructions:**
- Analyze the error, the code, and the HTML.
- The corrected script must assign the final pandas DataFrame to a variable named `result`.
- Return ONLY the raw, corrected Python script.

**Corrected Code:**
"""
    raw_corrected_code = llm(prompt).strip()
    return _extract_python_code(raw_corrected_code)

def execute_fetch(code: str, url: str, task: str, execution_log: list, max_retries: int = 3) -> pd.DataFrame:
    """
    Executes pre-written Python scraping code with a self-correction loop and logs corrections.
    """
    logger.info(f"🚀 Starting code execution for URL: {url}")
    response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    html_snippet = soup.prettify()[:5000]

    current_code = textwrap.dedent(_extract_python_code(code))
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Scraping attempt {attempt + 1} of {max_retries}...")
            # --- NEW: Log the code before execution ---
            logger.info(f"Executing Fetch Code:\n---START-CODE---\n{current_code}\n---END-CODE---")
            
            local_vars = {
                "soup": soup,
                "pd": pd,
                "requests": requests,
                "result": None
            }

            exec(current_code, {}, local_vars)
            df = local_vars.get("result")

            if isinstance(df, pd.DataFrame):
                logger.info(f"✅ Scraping successful on attempt {attempt + 1}. DataFrame shape: {df.shape}")
                return df
            else:
                raise ValueError(f"Scraping code did not return a pandas DataFrame. Got type: {type(df)}")

        except Exception as e:
            logger.warning(f"⚠️ Scraping attempt {attempt + 1} failed: {e}")
            error_message = str(e)
            if attempt + 1 == max_retries:
                logger.error("❌ All scraping attempts failed.")
                raise RuntimeError(f"Scraping failed after {max_retries} attempts. Last error: {error_message}")
            
            corrected_code_raw = _correct_fetch_code(current_code, error_message, task, html_snippet)
            log_entry = f"--- Corrected Fetch Code (Attempt {attempt + 2}) ---\n{corrected_code_raw}"
            execution_log.append(log_entry)

            current_code = textwrap.dedent(corrected_code_raw)
    
    raise RuntimeError("Scraping tool failed to execute after all retries.")
