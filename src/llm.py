import os
import time
from dotenv import load_dotenv
from groq import Groq

# Load environment variables from .env located at project root
load_dotenv()


class GroqClient:
    """Wrapper class for managing client interactions with Groq API with rate-limit resiliency."""

    def __init__(self, model_name: str = None):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY missing. Please configure it in your root .env file."
            )

        self.client = Groq(api_key=api_key)
        self.model_name = model_name or os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")

    def generate_response(
        self, prompt_payload: str, max_retries: int = 3, delay: float = 3.0
    ) -> str:
        """Sends prompt payload to Groq API with max_tokens control and 429 retry handling."""
        for attempt in range(1, max_retries + 1):
            try:
                chat_completion = self.client.chat.completions.create(
                    messages=[
                        {
                            "role": "user",
                            "content": prompt_payload,
                        }
                    ],
                    model=self.model_name,
                    temperature=0.1,
                    max_tokens=600,  # Caps reservation under the 1000 OTPM rate-limit
                )
                return chat_completion.choices[0].message.content
            except Exception as e:
                error_msg = str(e)

                # Handle 429 Rate Limit
                if "429" in error_msg or "rate_limit_exceeded" in error_msg:
                    if attempt < max_retries:
                        print(
                            f"⚠️ [Attempt {attempt}/{max_retries}] Rate limit hit (429). Retrying in {delay}s..."
                        )
                        time.sleep(delay)
                        continue

                return f"Error communicating with AI service: {error_msg}"