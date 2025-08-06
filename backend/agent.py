# backend/agent.py

from .llm_agent import llm
# --- MODIFICATION: Import both tools ---
from .toolkits.fetch import extract_relevant_data
from .toolkits.analyze import analyze_data
from .toolkits.file_handler import extract_content
import re
import logging

logger = logging.getLogger(__name__)

def get_reasoning(task_text: str) -> str:
    """Gets the initial high-level plan from the LLM."""
    prompt = f"""
You are a helpful AI assistant designed to solve analytical tasks.

TOOLS AVAILABLE:
- fetch(url): Scrapes a web page to get a raw data table.
- analyze(data, task): Analyzes the data to answer questions.

YOUR TASK:
\"\"\"
{task_text}
\"\"\"

Plan your approach step by step. ONLY describe your plan. Do not call any tools yet.
"""
    return llm(prompt).strip()

def extract_url_from_reasoning(reasoning: str) -> str:
    """
    Extracts the first URL found in the reasoning text using a reliable regex.
    """
    # This is a more direct and efficient way to find the URL.
    match = re.search(r'(https?://[^\s`\'"]+)', reasoning)
    if match:
        url = match.group(1)
        logger.info(f"🔍 Extracted URL using regex: {url}")
        return url
    logger.warning("⚠️ No URL found in reasoning.")
    return None

def handle_task(task_text: str, attachments: dict = None) -> dict:
    """
    Main agent logic that orchestrates the fetch and analyze tools.
    """
    attachments = attachments or {}
    logger.info("📥 Received task: %s", task_text.strip())

    # --- Step 1: Combine task text with any file attachments ---
    extracted_files_content = []
    if attachments:
        logger.info("📂 Extracting attached files...")
        for filename, content in attachments.items():
            try:
                # Assuming extract_content returns text for .txt files
                extracted_text = extract_content(filename, content)
                if isinstance(extracted_text, str):
                     extracted_files_content.append(f"---\nContent from {filename}\n\n{extracted_text.strip()}")
                else:
                    # Handle cases where attachments might be dataframes directly
                    logger.warning(f"Attachment {filename} was not text, skipping for now.")
            except Exception as e:
                logger.error(f"❌ Failed to extract from {filename}: {e}")

    full_task_text = task_text.strip()
    if extracted_files_content:
        full_task_text += "\n\n--- ADDITIONAL CONTEXT FROM ATTACHED FILES ---\n" + "\n\n".join(extracted_files_content)


    # --- Step 2: Get a high-level plan and extract the URL ---
    reasoning = get_reasoning(full_task_text)
    logger.info(f"🧠 Agent Reasoning:\n{reasoning}")
    url = extract_url_from_reasoning(reasoning)

    # Initialize results dictionary to track the process
    results = {
        "task": full_task_text,
        "reasoning": reasoning,
        "dataframe_preview": None,
        "final_answers": None,
        "error": None
    }

    if not url:
        results["error"] = "Could not identify a URL to scrape from the task."
        logger.error(results["error"])
        return results

    try:
        # --- Step 3: Call the 'fetch' tool to get the data ---
        logger.info("--- Calling Fetch Tool ---")
        scraped_df = extract_relevant_data(url, full_task_text)
        results["dataframe_preview"] = scraped_df.head().to_markdown()
        logger.info("✅ Fetch tool completed.")

        # --- Step 4: Call the 'analyze' tool with the scraped data ---
        logger.info("--- Calling Analyze Tool ---")
        final_answers = analyze_data(scraped_df, full_task_text)
        results["final_answers"] = final_answers
        logger.info(f"✅✅✅ Task completed successfully! Final answers: {final_answers}")

    except Exception as e:
        logger.error(f"🔥🔥🔥 Agent execution failed: {e}", exc_info=True)
        results["error"] = str(e)

    return results
