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
