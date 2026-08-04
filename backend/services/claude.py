import anthropic
import os
import traceback
from dotenv import load_dotenv
from typing import Any

load_dotenv()

# Latest and most powerful Claude model
MODEL = "claude-opus-4-7"


def get_client():
    api_key = os.getenv("ANTHROPIC_API_KEY")

    print(f"[Claude] API Key exists: {bool(api_key)}")

    return anthropic.Client(
        api_key=api_key
    )


def _extract_claude_text(response: Any) -> str | None:
    if response is None:
        return None

    if hasattr(response, "content"):
        content = response.content

        if isinstance(content, (list, tuple)) and len(content) > 0:
            item = content[0]

            if hasattr(item, "text"):
                return item.text

            if isinstance(item, dict):
                return item.get("text")

        if isinstance(content, str):
            return content

    if isinstance(response, str):
        return response

    if hasattr(response, "text"):
        return response.text

    return str(response)


def ask_claude(prompt: str, conversation_history: list = None) -> str:
    """
    Send any prompt to Claude Opus 4.7 and return plain text.
    """

    try:
        print(f"\n[Claude] Sending request to {MODEL}")
        print(f"[Claude] Prompt length: {len(prompt)} characters")

        messages = []

        # Add previous conversation
        if conversation_history:
            messages.extend(conversation_history)

        # Add current prompt
        messages.append({
            "role": "user",
            "content": prompt
        })

        client = get_client()

        message = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system="""
You are an expert assistant for Indian renewable energy policy documents.
Always follow the formatting instructions in the user prompt.
Never hallucinate numbers, incentives, legal provisions, tariffs, capacities, or dates.
If information is unavailable, explicitly say so.
""",
            messages=messages
        )

        response_text = _extract_claude_text(message)

        if response_text and response_text.strip():
            print("[Claude] Response received successfully.")
            return response_text.strip()

        print("[Claude] Empty response received.")
        return "failed: Empty response from Claude"

    except anthropic.AuthenticationError as e:
        print(f"[Claude] Authentication Error: {e}")
        return f"failed: AuthenticationError: {str(e)}"

    except anthropic.RateLimitError as e:
        print(f"[Claude] Rate Limit Error: {e}")
        return f"failed: RateLimitError: {str(e)}"

    except anthropic.APIStatusError as e:
        print(f"[Claude] API Status Error: {e}")
        return f"failed: APIStatusError: {str(e)}"

    except anthropic.BadRequestError as e:
        print(f"[Claude] Bad Request Error: {e}")
        return f"failed: BadRequestError: {str(e)}"

    except Exception as e:
        print("\n========== CLAUDE ERROR ==========")
        print("Error type:", type(e))
        print("Error:", repr(e))
        traceback.print_exc()
        print("==================================\n")

        return f"failed: {type(e).__name__}: {str(e)}"