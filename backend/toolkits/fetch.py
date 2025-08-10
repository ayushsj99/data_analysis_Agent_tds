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
    
    import traceback
    
    # Extract key HTML structure elements for context
    html_text = str(soup)
    
    # Extract key structural elements (much smaller context)
    key_elements = []
    
    # Get main structural tags
    for tag in ['header', 'nav', 'main', 'section', 'article', 'div', 'table']:
        elements = soup.find_all(tag, limit=3)  # Only first 3 of each
        for elem in elements:
            if elem.get('class') or elem.get('id'):
                key_elements.append(f"<{tag} class='{elem.get('class')}' id='{elem.get('id')}'>")
    
    # Limit to 500 characters total
    html_context = '\n'.join(key_elements)[:500]
    
    # Enhanced table detection and context (limited)
    table_context = ""
    tables = soup.find_all('table')
    if tables:
        table_context = f"\n\nTABLES FOUND: {len(tables)} table(s)\n"
        # Only show info for first 2 tables to keep prompt small
        for i, table in enumerate(tables[:2]):
            # Get table headers (limit to 10)
            headers = []
            header_row = table.find('tr')
            if header_row:
                headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])[:10]]
            
            # Get just 1 sample row
            rows = table.find_all('tr')[1:2]  # Only 1 sample row
            sample_data = []
            for row in rows:
                cells = [td.get_text(strip=True)[:20] for td in row.find_all(['td', 'th'])[:10]]  # Truncate cell content
                sample_data.append(cells)
            
            table_context += f"Table {i+1}: Headers={headers[:5]}, Sample={sample_data}, Rows≈{len(table.find_all('tr'))}\n"
    
    # Truncate error context to essential info only
    error_context = ""
    if previous_error:
        error_lines = previous_error.split('\n')
        # Keep only the last few lines of the error (most relevant)
        essential_error = '\n'.join(error_lines[-3:])[:300]
        error_context = f"\n\nPREVIOUS ERROR: {essential_error}"

    prompt = f"""
You are an expert Python scraping assistant. Your primary method failed, so you must now write manual scraping code.

TASK: {task_description}

WEBSITE STRUCTURE:
{html_context}
{table_context}

BASIC HTML PREVIEW (first 800 chars):
{soup.prettify()[:800]}
{error_context}

INSTRUCTIONS:
1. Analyze the HTML structure to understand the layout
2. Write Python code using BeautifulSoup and pandas
3. Use the pre-populated `soup` variable
4. Extract data matching the TASK exactly
5. Assign final DataFrame to variable named `result`
6. Handle data cleaning and validation
7. **Output ONLY raw Python code**

VALIDATION: Ensure DataFrame is relevant to task, has proper columns, and contains meaningful data.
"""
    raw_code = llm(prompt)
    return extract_python_code(raw_code)

def extract_relevant_data(url: str, task_description: str, max_retries: int = 10) -> pd.DataFrame:
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

        # If multiple tables, ask LLM to pick the right one (optimized prompt)
        selection_prompt = f"""
Select the most relevant table for this task: "{task_description}"

Found {len(tables)} tables:
"""
        for i, df in enumerate(tables):
            # Show only essential information - much smaller preview
            preview_rows = min(5, len(df))  # Only 5 rows max
            table_preview = df.head(preview_rows).to_string(max_rows=5, max_cols=10, max_colwidth=15)
            
            # Basic table information only
            table_info = f"Shape: {df.shape}"
            column_names = f"Columns: {list(df.columns)[:10]}"  # Max 10 columns
            
            selection_prompt += f"""
Table {i}: {table_info} | {column_names}
Preview:
{table_preview[:500]}  

"""
        
        selection_prompt += "Return ONLY the table index number (0, 1, 2, etc.)."

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
            
            # Validate that the result is appropriate for the task
            if isinstance(df, pd.DataFrame) and not df.empty:
                # Check if the scraped data is relevant to the task
                logger.info(f"✅ Generated DataFrame with shape {df.shape}")
                logger.info(f"DataFrame columns: {list(df.columns)}")
                logger.info(f"Sample data:\n{df.head().to_string()}")
                
                # Additional validation: check if DataFrame has meaningful data
                if len(df.columns) > 0 and len(df) > 0:
                    logger.info(f"✅ Fallback LLM generation succeeded on attempt {attempt + 1}.")
                    return df
                else:
                    raise ValueError("Generated DataFrame is empty or has no columns.")
            elif isinstance(df, pd.DataFrame):
                raise ValueError("Generated DataFrame is empty.")
            else:
                raise ValueError("Fallback code did not return a DataFrame.")
                
        except Exception as e:
            import traceback
            full_traceback = traceback.format_exc()
            # Keep only essential error info to avoid huge prompts
            error_summary = f"{type(e).__name__}: {str(e)}"
            logger.warning(f"⚠️ Fallback attempt {attempt + 1} failed: {error_summary}")
            error_log = error_summary  # Pass only summary instead of full traceback

    raise RuntimeError("All scraping strategies failed.")
