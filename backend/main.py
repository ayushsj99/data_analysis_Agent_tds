# backend/main.py

import logging
from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from backend.agent import handle_task
from dotenv import load_dotenv

# ==================== LOGGING CONFIGURATION ====================
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
# ===================================================================

load_dotenv()

logger = logging.getLogger(__name__)

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static + Templates
app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")
templates = Jinja2Templates(directory="frontend")


@app.get("/", response_class=HTMLResponse)
async def homepage(request: Request):
    logger.info("GET / - Homepage requested.")
    return templates.TemplateResponse("index.html", {"request": request})



from typing import List
from fastapi import Depends

from fastapi import Form

@app.post("/", response_class=HTMLResponse)
async def analyze(
    request: Request,
    task: UploadFile = File(...),
    attachments: List[UploadFile] = File(None),
):
    logger.info("POST / - Analysis task received.")
    try:
        task_text = (await task.read()).decode("utf-8")
        logger.info("Task text successfully decoded.")

        attachments_dict = {}
        if attachments:
            for uploaded_file in attachments:
                if uploaded_file and uploaded_file.filename:
                    logger.info(f"Processing attachment: {uploaded_file.filename}")
                    content = await uploaded_file.read()
                    attachments_dict[uploaded_file.filename] = content
        else:
            logger.info("No attachments provided.")

        result = handle_task(task_text, attachments_dict)

        return templates.TemplateResponse("index.html", {
            "request": request,
            "task_text": result.get("task"),
            "reasoning": result.get("reasoning"),
            "dataframe_preview": result.get("dataframe_preview"),
            "final_answers": result.get("final_answers"),
            "error": result.get("error")
        })

    except Exception as e:
        logger.error("An error occurred during analysis", exc_info=True)
        return templates.TemplateResponse("index.html", {
            "request": request,
            "error": str(e),
        })


@app.post("/api")
async def api_analyze(request: Request):
    """
    API endpoint that accepts any number of files of any format.
    Returns raw JSON response from the agent.
    
    Usage:
    curl "https://app.example.com/api/" -F "questions.txt=@question.txt" -F "image.png=@image.png" -F "data.csv=@data.csv"
    """
    logger.info("POST /api - API analysis task received.")
    
    try:
        # Get form data from request
        form_data = await request.form()
        
        # Find the task/question file (look for .txt files or files with 'question' in name)
        task_text = None
        task_file = None
        attachments_dict = {}
        
        # Process all uploaded files from form data
        for field_name, uploaded_file in form_data.items():
            if hasattr(uploaded_file, 'filename') and uploaded_file.filename:
                logger.info(f"Processing file: {uploaded_file.filename} (field: {field_name})")
                content = await uploaded_file.read()
                
                # Determine if this is the task file
                filename_lower = uploaded_file.filename.lower()
                if (filename_lower.endswith('.txt') or 
                    'question' in filename_lower or 
                    'task' in filename_lower or 
                    'prompt' in filename_lower):
                    
                    if task_text is None:  # Use the first matching file as task
                        task_text = content.decode("utf-8")
                        task_file = uploaded_file.filename
                        logger.info(f"Using {uploaded_file.filename} as task file")
                    else:
                        # If we already have a task, treat additional text files as attachments
                        attachments_dict[uploaded_file.filename] = content
                else:
                    # All other files are attachments
                    attachments_dict[uploaded_file.filename] = content
        
        # If no clear task file found, use the first file that can be decoded as text
        if task_text is None and form_data:
            # Get the first file from form data
            for field_name, uploaded_file in form_data.items():
                if hasattr(uploaded_file, 'filename') and uploaded_file.filename:
                    try:
                        content = await uploaded_file.read()
                        task_text = content.decode("utf-8")
                        task_file = uploaded_file.filename
                        logger.info(f"Using first file {uploaded_file.filename} as task file")
                        # Remove from attachments if it was added
                        attachments_dict.pop(uploaded_file.filename, None)
                        break
                    except UnicodeDecodeError:
                        # If can't decode as text, treat as attachment and try next file
                        attachments_dict[uploaded_file.filename] = content
                        continue
            
            # If still no task text found, use default
            if task_text is None:
                task_text = "Analyze the uploaded files"
                logger.info("No text file found, using default task")
        
        if task_text is None:
            return {
                "error": "No task file provided. Please include a .txt file with your question or a file with 'question' in the name."
            }
        
        logger.info(f"Task text successfully extracted from {task_file}")
        logger.info(f"Processing {len(attachments_dict)} attachment files")
        
        # Call the agent
        result = handle_task(task_text, attachments_dict)
        
        # Return only the final answers
        if isinstance(result, dict) and "final_answers" in result:
            return result["final_answers"]
        else:
            # Fallback if result structure is different
            return result

    except Exception as e:
        logger.error("An error occurred during API analysis", exc_info=True)
        return {
            "error": str(e)
        }
