# Data Analyst Agent

An LLM-powered agent that analyzes arbitrary data tasks via natural language prompts.

## Deploy on Hugging Face
Supports `.txt` input with instructions and returns JSON answers + plots.

data-analyst-agent/
├── backend/
│   ├── main.py                 # FastAPI app entry point
│   ├── agent.py                # Task handler logic (core pipeline logic)
│   ├── llm_agent.py            # Direct Gemini API wrapper (via `google.generativeai`)
│   ├── schemas.py              # Pydantic models for request/response
│   ├── toolkits/
│   │   ├── summarize.py        # LLM-based summarizer
│   │   ├── sql_generator.py    # Generate SQL queries using LLM
│   │   ├── file_handler.py     # Extract content from .txt, .pdf, .csv, .xlsx
│   │   ├── fetch.py            # Scrape and clean data from web sources
│   │   ├── analyze.py          # Structured data analysis logic
│   │   └── visualize.py        # Base64 image plots for Rank vs Peak
├── frontend/
│   ├── index.html              # Bootstrap + Jinja frontend for file upload + result display
│   └── styles.css              # Optional custom styles
├── .env                        # Your API keys and env vars
├── requirements.txt
└── README.md
