from google import genai
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize Gemini client with your API key
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

def llm(prompt: str) -> str:
    """
    Basic wrapper to call Gemini LLM with a prompt.
    Returns the response as plain text.
    """
    try:
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        return response.text.strip()
    except Exception as e:
        return f"LLM error: {str(e)}"
