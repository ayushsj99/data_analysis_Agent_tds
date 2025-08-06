# backend/toolkits/fetch.py

import pandas as pd
import requests
from bs4 import BeautifulSoup
from backend.llm_agent import llm
import re
import logging
from io import StringIO # Required for pandas.read_html from string

logger = logging.getLogger(__name__)

def extract_python_code(llm_response: str) -> str:
    """Extracts Python code from an LLM response."""
    match = re.search(r'```(?:python\n)?(.*)```', llm_response, re.DOTALL)
    if match:
        return match.group(1).strip()
    return llm_response.strip()

def llm_generate_scraping_code(soup: BeautifulSoup, task_description: str, previous_error: str = "") -> str:
    """Generates scraping code as a fallback."""
    logger.info("🤖 Falling back to LLM code generation for scraping...")
    
    error_context = f"\n\nA previous attempt failed with this error, please fix it:\n{previous_error}" if previous_error else ""

    prompt = f"""
You are an expert Python scraping assistant. Your primary method failed, so you must now write manual scraping code.

HTML SNIPPET:
---
{soup.prettify()[:5000]}
---

TASK:
---
{task_description}
---
{error_context}

INSTRUCTIONS:
1.  Write a Python script using the `BeautifulSoup` and `pandas` libraries.
2.  The script will have access to a pre-populated `soup` variable.
3.  The script MUST assign the final, raw pandas DataFrame to a variable named `result`.
4.  **IMPORTANT: Your output must be ONLY the raw Python code.**
"""
    raw_code = llm(prompt)
    return extract_python_code(raw_code)

def extract_relevant_data(url: str, task_description: str, max_retries: int = 2) -> pd.DataFrame:
    """
    Extracts a relevant DataFrame from a URL.
    
    Strategy:
    1.  Tries the robust `pandas.read_html()` method first.
    2.  If multiple tables are found, asks an LLM to choose the best one.
    3.  If `read_html` fails, falls back to the LLM generating code from scratch.
    """
    logger.info(f"🚀 Starting robust data extraction from URL: {url}")
    response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    response.raise_for_status()

    # --- STRATEGY 1: Use pandas.read_html (fast and reliable) ---
    try:
        logger.info("Attempting to parse tables with pandas.read_html...")
        # We use StringIO to avoid the FutureWarning
        tables = pd.read_html(StringIO(response.text))
        
        if not tables:
            raise ValueError("pandas.read_html found no tables on the page.")

        logger.info(f"✅ Found {len(tables)} tables. Asking LLM to select the best one.")

        if len(tables) == 1:
            logger.info("Only one table found, returning it directly.")
            return tables[0]

        # If multiple tables, ask LLM to pick the right one
        selection_prompt = f"""
You are an expert data assistant. I have extracted {len(tables)} tables from a webpage.
Based on the user's task, please tell me which table index (0, 1, 2, etc.) is the most relevant.

USER TASK:
"{task_description}"

TABLE PREVIEWS:
---
"""
        for i, df in enumerate(tables):
            selection_prompt += f"TABLE INDEX {i}:\n{df.head().to_string()}\n\n---\n"
        
        selection_prompt += "Return ONLY the integer index of the most relevant table."

        llm_response = llm(selection_prompt).strip()
        best_index = int(re.search(r'\d+', llm_response).group())
        
        logger.info(f"✅ LLM selected table index: {best_index}. Returning it.")
        return tables[best_index]

    except Exception as e:
        logger.warning(f"⚠️ pandas.read_html strategy failed: {e}. Falling back to LLM code generation.")

    # --- STRATEGY 2: Fallback to LLM generating code ---
    soup = BeautifulSoup(response.text, 'html.parser')
    error_log = ""
    for attempt in range(max_retries):
        logger.info(f"Fallback attempt {attempt + 1} of {max_retries}...")
        scraping_code = llm_generate_scraping_code(soup, task_description, error_log)
        
        try:
            local_vars = {"soup": soup, "pd": pd, "result": None}
            exec(scraping_code, {}, local_vars)
            df = local_vars.get("result")
            if isinstance(df, pd.DataFrame):
                logger.info(f"✅ Fallback LLM generation succeeded on attempt {attempt + 1}.")
                return df
            raise ValueError("Fallback code did not return a DataFrame.")
        except Exception as e:
            logger.warning(f"⚠️ Fallback attempt {attempt + 1} failed: {e}")
            error_log = str(e)

    raise RuntimeError("All scraping strategies failed.")
