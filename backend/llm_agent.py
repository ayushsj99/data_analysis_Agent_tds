from google import genai
from openai import OpenAI  # Updated import
import os
from dotenv import load_dotenv

load_dotenv()

# Load environment variables
LLM_PROVIDER ="openai"

# Initialize Gemini (keep as is)
gemini_client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

# Initialize OpenAI client properly
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def llm(prompt: str) -> str:
    """
    Unified LLM interface using either Gemini or OpenAI based on env config.
    """
    try:
        if LLM_PROVIDER == "gemini":
            # GEMINI: Keep code untouched
            response = gemini_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            return response.text.strip()
        
        elif LLM_PROVIDER == "openai":
            # CORRECTED OPENAI IMPLEMENTATION
            # Option 1: Using Chat Completions API (recommended and stable)
            response = openai_client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return response.choices[0].message.content.strip()
            
            # Option 2: Using Responses API (if you specifically need it)
            # response = openai_client.responses.create(
            #     model="gpt-4o-mini",
            #     input=prompt
            # )
            # return response.output_text.strip()
        
        else:
            return f"LLM error: Unknown provider '{LLM_PROVIDER}'"

    except Exception as e:
        return f"LLM error: {str(e)}"

def llm_vision(prompt: str, image_path: str) -> str:
    """
    LLM interface for vision tasks - sends image with prompt to LLM.
    """
    try:
        if LLM_PROVIDER == "gemini":
            # Read and encode image
            import base64
            import mimetypes
            
            # Detect MIME type
            mime_type, _ = mimetypes.guess_type(image_path)
            if not mime_type or not mime_type.startswith('image/'):
                mime_type = "image/jpeg"  # Default fallback
            
            with open(image_path, "rb") as image_file:
                image_data = base64.b64encode(image_file.read()).decode('utf-8')
            
            # Create content with image and text
            response = gemini_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    {
                        "parts": [
                            {"text": prompt},
                            {
                                "inline_data": {
                                    "mime_type": mime_type,
                                    "data": image_data
                                }
                            }
                        ]
                    }
                ]
            )
            return response.text.strip()
        
        elif LLM_PROVIDER == "openai":
            # OpenAI Vision API
            import base64
            import mimetypes
            
            # Detect MIME type for data URI
            mime_type, _ = mimetypes.guess_type(image_path)
            if not mime_type or not mime_type.startswith('image/'):
                mime_type = "image/jpeg"  # Default fallback
            
            with open(image_path, "rb") as image_file:
                image_data = base64.b64encode(image_file.read()).decode('utf-8')
            
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",  # or gpt-4-vision-preview
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{image_data}"
                                }
                            }
                        ]
                    }
                ]
            )
            return response.choices[0].message.content.strip()
        
        else:
            return f"LLM Vision error: Unknown provider '{LLM_PROVIDER}'"

    except Exception as e:
        return f"LLM Vision error: {str(e)}"



