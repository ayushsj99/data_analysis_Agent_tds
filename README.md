# Data Analysis Agent (TDS Project)

A robust, LLM-powered data analysis agent that can autonomously process, analyze, and visualize data from a wide variety of file types (CSV, Excel, PDF, images, etc.) and web sources. The agent uses advanced planning and tool orchestration to answer complex user questions, generate code, and return results in the requested format.

## 🚀 Quick Start with Hugging Face Spaces

### Deploy to Hugging Face Spaces

1. **Create a new Space:**
   - Go to [Hugging Face Spaces](https://huggingface.co/spaces)
   - Click "Create new Space"
   - Choose "Docker" as the SDK
   - Upload your project files

2. **Set Environment Variables:**
   ```bash
   OPENAI_API_KEY=your_openai_api_key_here
   GOOGLE_API_KEY=your_google_api_key_here  # Optional for Gemini
   ```

3. **Your Space will automatically:**
   - Build the Docker container
   - Install all dependencies
   - Start the web application on port 7860

### Local Docker Deployment

```bash
# Build the Docker image
docker build -t data-analysis-agent .

# Run the container
docker run -p 7860:7860 \
  -e OPENAI_API_KEY=your_key_here \
  -e GOOGLE_API_KEY=your_key_here \
  data-analysis-agent
```

## Features
- **Multi-file Upload:** Upload any number of files (CSV, Excel, PDF, images, etc.) for analysis.
- **Automatic Tool Selection:** The agent intelligently chooses the right tool (file handler, DuckDB, web fetch, etc.) based on your question and the uploaded files.
- **LLM-Powered Planning:** Uses OpenAI/Gemini to generate step-by-step plans and code for data extraction, cleaning, analysis, and visualization.
- **Robust File Handling:** Previews, validates, and extracts content from all major file types. Handles file name mismatches and missing columns gracefully.
- **Web Data Support:** Can fetch and analyze data from URLs and web tables.
- **Visualization:** Returns plots and images as base64-encoded data URIs for direct rendering in the frontend.
- **Error Correction:** Automatically retries and corrects code using LLM-based debugging if an error occurs.
- **Modern Frontend:** Clean, Bootstrap-based web UI for uploading tasks and files, and viewing results.

## Requirements
- Python 3.11+
- Docker (for containerized deployment)
- OpenAI API key or Google API key for LLM access

### Python dependencies
Install all required Python packages:
```bash
pip install -r requirements.txt
```

## Local Development

### 1. Start the Backend
Run the FastAPI backend (from the project root):
```bash
uvicorn backend.main:app --reload --port 7860
```

### 2. Open the Frontend
Open your browser and go to:
```
http://localhost:7860/
```

### 3. Submit a Task
- Upload a `.txt` file describing your data analysis question or task.
- (Optional) Upload any number of data files (CSV, Excel, PDF, images, etc.) as attachments.
- Click **Submit for Analysis**.

### 4. View Results
- The agent will display its plan, code, data previews, and final answers (including plots/images as inline previews).
- Errors and logs are shown for transparency and debugging.

## Docker Configuration

The project includes optimized Docker configuration for production deployment:

- **Multi-stage build** for smaller image size
- **System dependencies** for PDF processing, image handling, and scientific computing
- **Security hardening** with non-root user
- **Health checks** for monitoring
- **Proper caching** with .dockerignore
- **Environment variable support** for API keys

## Environment Variables

- `OPENAI_API_KEY`: Your OpenAI API key (required if using OpenAI)
- `GOOGLE_API_KEY`: Your Google Generative AI API key (required if using Gemini)
- `LLM_PROVIDER`: Set to "openai" or "gemini" (defaults to "openai")
- `MPLBACKEND`: Set to "Agg" for server environments (auto-configured in Docker)

## Example Task
**Task file (`task.txt`):**
```
Dataset: Global Airport Passenger Traffic (Excel)

Description:
This Excel dataset contains fictional records representing passengers from various countries.
We will treat the "Country" column as the passenger's departure country for the purpose of this analysis.

Key columns:
- First Name (string)
- Last Name (string)
- Email (string)
- Gender (string)
- Country (string)
- Age (integer)

Sample row:
John,Doe,john.doe@example.com,Male,United States,34

Questions:
{
  "Which country has the most passengers in the dataset?": "...",
  "What's the average age of passengers from 'India'?": "...",
  "Plot age distribution of passengers from 'India' as a histogram. Encode as base64 PNG data URI under 100,000 chars": "data:image/png;base64,..."
}
```
**Attachment:** `q1.xlsx` (the Excel file)

## Advanced
- The agent supports DuckDB/SQL queries if explicitly requested in the task.
- All uploaded images are previewed as base64 in the plan context and results.
- The backend logs all task and file details for traceability.

## Troubleshooting
- Ensure your uploaded files match the description in your task file (column names, format, etc.).
- If you see errors about missing columns, check your data file structure.
- For PDF/image extraction, results depend on file quality and LLM capabilities.

## License
MIT License

---

**Developed for IITM TDS Project 2**
