# backend/llm_agent.py

import os
from dotenv import load_dotenv
from google import genai
import openai # <-- 1. Import the OpenAI library

load_dotenv()

# --- Client Initialization ---
# Initialize the Google Gemini client
google_client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

# Initialize the OpenAI client
# The library automatically looks for the OPENAI_API_KEY environment variable
openai_client = openai.OpenAI()


def llm(prompt: str, provider: str = "google") -> str:
    """
    Wrapper to call a specified LLM with a prompt.
    Returns the response as plain text.

    Args:
        prompt (str): The prompt to send to the model.
        provider (str): The LLM provider to use, either "google" or "openai".
                        Defaults to "google".

    Returns:
        str: The LLM's response text.
    """
    try:
        # --- 2. Add logic to choose the provider ---
        if provider.lower() == "openai":
            # Use the OpenAI client
            # Note: The model name 'gpt-4o' is a good, fast, and powerful choice.
            # You can change this to 'gpt-3.5-turbo' for more speed or 'gpt-4-turbo' for more power.
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system", 
                        "content": "You're a precise and efficient Data Analyst Agent. Given a task description and files (CSV, JSON, image, etc.), analyze the data, generate correct answers, and return them in the exact format requested (JSON, base64 plot, etc.) within 3 minutes. Never hallucinate, follow instructions strictly, and ensure all visual or numerical outputs are accurate and compact."
                    },
                    {"role": "user", "content": prompt},
                ]
            )
            return response.choices[0].message.content.strip()

        elif provider.lower() == "google":
            # Use the Google Gemini client (your existing logic)
            response = google_client.models.generate_content(
                model="gemini-2.5-flash", 
                contents=prompt
            )
            return response.text.strip()
            
        else:
            raise ValueError(f"Unknown LLM provider: {provider}. Please choose 'google' or 'openai'.")

    except Exception as e:
        # Generic error handling for both clients
        return f"LLM error with provider '{provider}': {str(e)}"

