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
from backend.llm_agent import llm, llm_vision
from .fetch import extract_python_code

# For images and PDFs
from PIL import Image
import pdfplumber

# Note: OCR libraries will be imported dynamically by the LLM when text extraction from images is needed

logger = logging.getLogger(__name__)

def _preview_file(file_path: str, file_type: str, max_rows: int = 5) -> str:
    """
    Generate a comprehensive preview string for the file based on its type.
    """
    try:
        file_size = os.path.getsize(file_path)
        size_mb = file_size / (1024 * 1024)
        
        if file_type == 'csv':
            # Enhanced CSV preview with memory optimization
            chunk_size = 1000 if size_mb > 50 else None
            if chunk_size:
                df = pd.read_csv(file_path, nrows=max_rows * 2)  # Read more for better preview
                logger.info(f"Large CSV file ({size_mb:.1f}MB) - using optimized preview")
            else:
                df = pd.read_csv(file_path)
            
            buffer = io.StringIO()
            df.info(buf=buffer)
            info = buffer.getvalue()
            
            # Enhanced preview with statistics
            numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
            text_cols = df.select_dtypes(include=['object']).columns.tolist()
            
            preview = f"--- File Info ---\nSize: {size_mb:.1f}MB, Rows: {len(df)}, Columns: {len(df.columns)}\n"
            preview += f"Numeric columns: {numeric_cols[:5]}{'...' if len(numeric_cols) > 5 else ''}\n"
            preview += f"Text columns: {text_cols[:5]}{'...' if len(text_cols) > 5 else ''}\n\n"
            preview += f"--- Head ({max_rows} rows) ---\n{df.head(max_rows).to_markdown()}\n"
            preview += f"--- Tail ({max_rows} rows) ---\n{df.tail(max_rows).to_markdown()}\n"
            preview += f"--- DataFrame Info ---\n{info}"
            return preview
        elif file_type == 'excel':
            # Enhanced Excel preview with multi-sheet support
            excel_file = pd.ExcelFile(file_path)
            sheet_names = excel_file.sheet_names
            
            if len(sheet_names) > 1:
                preview = f"--- Excel File Info ---\nSize: {size_mb:.1f}MB, Sheets: {len(sheet_names)}\nSheet names: {sheet_names}\n\n"
                for i, sheet in enumerate(sheet_names[:3]):  # Preview first 3 sheets
                    try:
                        df = pd.read_excel(file_path, sheet_name=sheet, nrows=max_rows)
                        preview += f"--- Sheet '{sheet}' Preview ---\n"
                        preview += f"Shape: {df.shape}\n"
                        preview += f"{df.head(max_rows).to_markdown()}\n\n"
                    except Exception as e:
                        preview += f"--- Sheet '{sheet}' ---\nError reading sheet: {str(e)}\n\n"
                if len(sheet_names) > 3:
                    preview += f"... and {len(sheet_names) - 3} more sheets\n"
            else:
                df = pd.read_excel(file_path, sheet_name=sheet_names[0])
                buffer = io.StringIO()
                df.info(buf=buffer)
                info = buffer.getvalue()
                preview = f"--- Excel File Info ---\nSize: {size_mb:.1f}MB, Single sheet: '{sheet_names[0]}'\n"
                preview += f"--- Head ---\n{df.head(max_rows).to_markdown()}\n--- Tail ---\n{df.tail(max_rows).to_markdown()}\n--- Info ---\n{info}"
            return preview
        elif file_type == 'image':
            with Image.open(file_path) as img:
                return f"Image format: {img.format}, Size: {img.size}, Mode: {img.mode}\nNote: Can extract text (OCR) or provide image description based on task requirements."
        elif file_type == 'pdf':
            # Enhanced PDF preview with table detection
            try:
                with pdfplumber.open(file_path) as pdf:
                    num_pages = len(pdf.pages)
                    first_page_text = pdf.pages[0].extract_text() if num_pages > 0 else ''
                    
                    # Check for tables across all pages (not just first 5)
                    total_tables = 0
                    table_pages = []
                    for i, page in enumerate(pdf.pages):  # Check ALL pages
                        tables = page.extract_tables()
                        if tables:
                            total_tables += len(tables)
                            table_pages.append(i + 1)
                    
                    preview = f"--- PDF File Info ---\nSize: {size_mb:.1f}MB, Pages: {num_pages}\n"
                    preview += f"Tables detected: {total_tables} across pages {table_pages}\n\n"
                    preview += f"--- First Page Text Preview ---\n{first_page_text[:1000]}..."
                    
                    if total_tables > 0:
                        preview += f"\n\n--- Table Extraction Capability ---\nDetected {total_tables} tables that can be extracted as DataFrames"
                    
                    return preview
            except Exception as e:
                return f"PDF file ({size_mb:.1f}MB, error reading: {str(e)[:100]})"
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

**CRITICAL RETURN FORMAT REQUIREMENTS:**
- **For TABLE DATA (CSV, Excel, PDF tables, any structured/tabular data)**: The `result` variable MUST be a pandas DataFrame object, never a dictionary, list, or other format.
- **For TEXT DATA (PDF text content, plain text extraction, document content)**: The `result` variable MUST be a string object.
- **For MIXED DATA (Excel with multiple sheets, PDF with multiple tables)**: Return a dictionary where keys are descriptive names (e.g., sheet names, table names) and values are pandas DataFrames.

**Instructions:**
- Carefully analyze the error traceback, the failed code, and the file preview.
- The corrected script must successfully complete the original task.
- The script must assign the final answer to a variable named `result`.
- **STRICTLY FOLLOW the return format requirements above** - use pandas DataFrame for table data, string for text data.
- **For PDFs**: Use appropriate libraries (pdfplumber, tabula-py, camelot) to extract tables as DataFrames or text as strings based on the task requirements.
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

    # Handle images directly with LLM vision
    if file_type == 'image':
        logger.info("🖼️ Processing image with LLM vision...")
        vision_prompt = f"""
You are an expert image analyst. Based on the task description below, analyze this image and provide the requested information.

**Task Description:** {task_description}

**Full Context:** {full_task}

**Instructions:**
- If the task asks for TEXT EXTRACTION or OCR, extract and return all readable text from the image.
- If the task asks for IMAGE DESCRIPTION or ANALYSIS, provide a detailed description of what you see in the image.
- Return ONLY the requested information as a string, no additional formatting or explanations.
"""
        try:
            result = llm_vision(vision_prompt, file_path)
            logger.info("✅ Successfully processed image with LLM vision.")
            return result
        except Exception as e:
            logger.error(f"❌ LLM vision failed: {e}")
            return f"Error processing image: {str(e)}"


    # Handle non-image files with code generation
    # Extract page count for PDFs to include in prompt
    pdf_page_info = ""
    if file_type == 'pdf':
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                num_pages = len(pdf.pages)
                pdf_page_info = f" **CRITICAL FOR PDFs: This PDF has {num_pages} pages total - you MUST process ALL {num_pages} pages, not just the pages where tables were detected.**"
        except:
            pdf_page_info = " **CRITICAL FOR PDFs: Process ALL pages of the PDF.**"
    
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

**CRITICAL RETURN FORMAT REQUIREMENTS:**
- **For TABLE DATA (CSV, Excel, PDF tables, any structured/tabular data)**: The `result` variable MUST be a pandas DataFrame object, never a dictionary, list, or other format.
- **For TEXT DATA (PDF text content, plain text extraction, document content)**: The `result` variable MUST be a string object.
- **For MIXED DATA (Excel with multiple sheets, PDF with multiple tables)**: Return a dictionary where keys are descriptive names (e.g., sheet names, table names) and values are pandas DataFrames.

**INSTRUCTIONS:**
1. Carefully analyze the file preview and understand the file's structure and content.
2. Write a single, top-level Python script to perform all necessary processing, analysis, or extraction as required by the SPECIFIC PYTHON SCRIPT TASK above.
3. Read the file from the path '{file_path}'.
4. The script must assign the final answer to a variable named `result`.
5. **STRICTLY FOLLOW the return format requirements above** - use pandas DataFrame for table data, string for text data.
6. **For PDFs**: Use appropriate libraries (pdfplumber, tabula-py, camelot) to extract tables as DataFrames or text as strings based on the task requirements.{pdf_page_info}
   **CAMELOT USAGE**: Import camelot correctly: `import camelot` then use `camelot.read_pdf(file_path, pages='all', flavor='stream')` or `camelot.read_pdf(file_path, pages='all', flavor='lattice')`. If camelot fails, fallback to pdfplumber.
7. Output ONLY the raw Python code. Do not include explanations or markdown.

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
                "Image": Image, "pdfplumber": pdfplumber, "PdfReader": PdfReader, 
                "result": None
            }
            exec(code, local_vars)
            final_result = local_vars.get("result")
            if final_result is not None:
                # Validate return type based on task description (images handled separately)
                task_lower = task_description.lower()
                if any(keyword in task_lower for keyword in ["table", "dataframe", "tabular", "structured", "csv", "excel"]):
                    if not isinstance(final_result, (pd.DataFrame, dict)):
                        raise ValueError(f"Expected pandas DataFrame or dict of DataFrames for table data, got {type(final_result)}")
                elif any(keyword in task_lower for keyword in ["text", "content", "extract text", "document"]):
                    if not isinstance(final_result, str):
                        raise ValueError(f"Expected string for text data, got {type(final_result)}")
                
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
