# backend/main.py

import logging
from fastapi import FastAPI, Request, UploadFile, File
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


@app.post("/", response_class=HTMLResponse)
async def analyze(
    request: Request,
    task: UploadFile = File(...),
    attachment1: UploadFile = File(None),
    attachment2: UploadFile = File(None),
    attachment3: UploadFile = File(None),
):
    logger.info("POST / - Analysis task received.")
    try:
        task_text = (await task.read()).decode("utf-8")
        logger.info("Task text successfully decoded.")

        attachments = {}
        for i, uploaded_file in enumerate([attachment1, attachment2, attachment3]):
            if uploaded_file and uploaded_file.filename:
                logger.info(f"Processing attachment: {uploaded_file.filename}")
                content = await uploaded_file.read()
                attachments[uploaded_file.filename] = content
            else:
                logger.info(f"Attachment {i+1} not provided.")

        result = handle_task(task_text, attachments)

        # --- THIS IS THE CORRECTED SECTION ---
        # The result from handle_task is a dictionary. We pass its contents
        # to the template, now including the 'final_answers' key.
        return templates.TemplateResponse("index.html", {
            "request": request,
            "task_text": result.get("task"),
            "reasoning": result.get("reasoning"),
            "dataframe_preview": result.get("dataframe_preview"),
            "final_answers": result.get("final_answers"), # <-- THE FIX
            "error": result.get("error")
        })

    except Exception as e:
        logger.error("An error occurred during analysis", exc_info=True)
        return templates.TemplateResponse("index.html", {
            "request": request,
            "error": str(e),
        })
