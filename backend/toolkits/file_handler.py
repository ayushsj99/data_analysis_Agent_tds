import mimetypes
import pandas as pd
import base64
from PyPDF2 import PdfReader
from io import BytesIO

import logging
import io
import os
import json
import base64
import traceback
from backend.llm_agent import llm
from .fetch import extract_python_code

# For images and PDFs
from PIL import Image
import pdfplumber

logger = logging.getLogger(__name__)

def _preview_file(file_path: str, file_type: str, max_rows: int = 5) -> str:
    """
    Generate a preview string for the file based on its type.
    """
    try:
        if file_type == 'csv':
            df = pd.read_csv(file_path)
            buffer = io.StringIO()
            df.info(buf=buffer)
            info = buffer.getvalue()
            preview = f"--- Head ---\n{df.head(max_rows).to_markdown()}\n--- Tail ---\n{df.tail(max_rows).to_markdown()}\n--- Info ---\n{info}"
            return preview
        elif file_type == 'excel':
            df = pd.read_excel(file_path)
            buffer = io.StringIO()
            df.info(buf=buffer)
            info = buffer.getvalue()
            preview = f"--- Head ---\n{df.head(max_rows).to_markdown()}\n--- Tail ---\n{df.tail(max_rows).to_markdown()}\n--- Info ---\n{info}"
            return preview
        elif file_type == 'image':
            with Image.open(file_path) as img:
                return f"Image format: {img.format}, Size: {img.size}, Mode: {img.mode}"
        elif file_type == 'pdf':
            with pdfplumber.open(file_path) as pdf:
                num_pages = len(pdf.pages)
                first_page_text = pdf.pages[0].extract_text() if num_pages > 0 else ''
                return f"PDF with {num_pages} pages. First page text preview:\n{first_page_text[:500]}"
        else:
            return "Unknown file type."
    except Exception as e:
        return f"Error previewing file: {e}"

def _detect_file_type(file_path: str) -> str:
    ext = os.path.splitext(file_path)[-1].lower()
    if ext in ['.csv']:
        return 'csv'
    elif ext in ['.xls', '.xlsx']:
        return 'excel'
    elif ext in ['.png', '.jpg', '.jpeg', '.bmp', '.gif']:
        return 'image'
    elif ext in ['.pdf']:
        return 'pdf'
    else:
        return 'unknown'

def _correct_file_code(failed_code: str, error_message: str, task: str, file_preview: str, file_type: str) -> str:
    logger.info("🤖 Attempting to correct failed file handler code...")
    prompt = f"""
You are a Senior Python Data Scientist and expert code debugger.
The following Python script failed to execute. Your task is to analyze the error traceback and provide a corrected version of the script.

**Task:**
---
{task}
---

**File Type:** {file_type}

**File Preview:**
---
{file_preview}
---

**Failed Code:**
```python
{failed_code}
```

**Full Error Traceback:**
```
{error_message}
```

**Instructions:**
- Carefully analyze the error traceback, the failed code, and the file preview.
- The corrected script must successfully complete the original task.
- The script must assign the final answer to a variable named `result`.
- Return ONLY the raw, corrected Python script.

**Corrected Code:**
"""
    raw_corrected_code = llm(prompt).strip()
    return extract_python_code(raw_corrected_code)

def handle_file_task(task_description: str, full_task: str, file_path: str, max_retries: int = 3):
    """
    Receives a task description, the full task, and a file (csv, excel, image, pdf),
    generates and executes code to process the file and return the result as per the task.
    """
    logger.info("📁 Starting file handler...")
    file_type = _detect_file_type(file_path)
    file_preview = _preview_file(file_path, file_type)
    logger.info(f"File Preview:\n{file_preview}")


    base_prompt = f"""
You are a Senior Python Data Scientist. Your job is to generate a Python script to solve a specific data task on a file, based on the following context.

**OVERALL TASK CONTEXT:**
---
This is the full user request, which may include background, requirements, and desired output:
{full_task}
---

**SPECIFIC PYTHON SCRIPT TASK:**
---
This is the precise instruction for what the Python script you generate must accomplish:
{task_description}
---

**FILE INFORMATION:**
- File path: '{file_path}'
- File type: {file_type}

**FILE PREVIEW:**
---
{file_preview}
---

**INSTRUCTIONS:**
1. Carefully analyze the file preview and understand the file's structure and content.
2. Write a single, top-level Python script to perform all necessary processing, analysis, or extraction as required by the SPECIFIC PYTHON SCRIPT TASK above.
3. Read the file from the path '{file_path}'.
4. The script must assign the final answer to a variable named `result`. The format of `result` must match the user's requirements.
5. Output ONLY the raw Python code. Do not include explanations or markdown.

**YOUR SCRIPT:**
"""

    logger.info("🤖 Generating initial file handler code...")
    raw_code = llm(base_prompt)
    code = extract_python_code(raw_code)

    for attempt in range(max_retries):
        logger.info(f"File handler attempt {attempt + 1} of {max_retries}...")
        try:
            logger.info(f"Executing File Handler Code:\n---START-CODE---\n{code}\n---END-CODE---")
            local_vars = {
                "file_path": file_path,
                "pd": pd, "io": io, "os": os, "json": json, "base64": base64,
                "Image": Image, "pdfplumber": pdfplumber, "result": None
            }
            exec(code, local_vars)
            final_result = local_vars.get("result")
            if final_result is not None:
                logger.info("✅ Successfully executed file handler code.")
                if hasattr(final_result, 'item'):
                    return final_result.item()
                if isinstance(final_result, dict):
                    return {k: (v.item() if hasattr(v, 'item') else v) for k, v in final_result.items()}
                if isinstance(final_result, list):
                    return [item.item() if hasattr(item, 'item') else item for item in final_result]
                return final_result
            else:
                raise ValueError("File handler code did not assign a value to the 'result' variable.")
        except Exception as e:
            error_log = traceback.format_exc()
            logger.warning(f"⚠️ File handler attempt {attempt + 1} failed:\n{error_log}")
            logger.debug(f"---FAILING-FILE-HANDLER-CODE---\n{code}\n---END-CODE---")
            if attempt + 1 == max_retries:
                logger.error("❌ All file handler attempts failed.")
                raise RuntimeError(f"Failed to handle file after {max_retries} attempts. Last error: {e}")
            code = _correct_file_code(code, error_log, f"{task_description}\n{full_task}", file_preview, file_type)

    raise RuntimeError("File handler failed after all retries.")
import mimetypes
import pandas as pd
import base64
from PyPDF2 import PdfReader
from io import BytesIO


def detect_type(filename: str) -> str:
    ext = filename.lower().split(".")[-1]
    return {
        "csv": "csv",
        "json": "json",
        "xlsx": "excel",
        "xls": "excel",
        "pdf": "pdf",
        "png": "image",
        "jpg": "image",
        "jpeg": "image",
        "py": "python",
        "sql": "sql"
    }.get(ext, mimetypes.guess_type(filename)[0] or "unknown")


def extract_content(filename: str, content: bytes) -> str:
    file_type = detect_type(filename)

    if file_type == "csv":
        df = pd.read_csv(BytesIO(content))
        return df.head().to_markdown()
    elif file_type == "json":
        return content.decode("utf-8")
    elif file_type == "excel":
        df = pd.read_excel(BytesIO(content))
        return df.head().to_markdown()
    elif file_type == "pdf":
        reader = PdfReader(BytesIO(content))
        return "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
    elif file_type == "image":
        encoded = base64.b64encode(content).decode("utf-8")
        return f"data:image/png;base64,{encoded}"
    elif file_type == "python" or file_type == "sql":
        return content.decode("utf-8")
    else:
        return f"Unsupported file type: {file_type}"
