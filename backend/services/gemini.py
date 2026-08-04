# from google import genai
# import os
# import time
# from dotenv import load_dotenv

# load_dotenv()

# client = genai.Client(
#     api_key=os.getenv("GOOGLE_API_KEY")
# )

# # Models are tried in order.
# # - gemini-2.0-flash has a generous free tier (separate quota from 2.5)
# # - gemini-1.5-flash is the most permissive free tier fallback
# # - gemini-2.5-flash stays as primary
# # - gemini-2.5-pro removed (free tier quota is 0 — it will always fail)
# MODELS_TO_TRY = [
#     "gemini-2.5-flash",
#     "gemini-2.0-flash",
#     "gemini-1.5-flash",
# ]

# # How long to wait between retries per model (seconds)
# RETRY_DELAY = 3

# # If a model returns 429 (quota exhausted), skip all retries for that model
# # and move immediately to the next one — no point retrying a quota error.
# SKIP_ON_429 = True


# def _is_quota_error(e: Exception) -> bool:
#     """Returns True if the error is a hard quota limit (429 RESOURCE_EXHAUSTED)."""
#     msg = str(e)
#     return "429" in msg or "RESOURCE_EXHAUSTED" in msg


# def _is_overload_error(e: Exception) -> bool:
#     """Returns True if the error is a temporary server overload (503 UNAVAILABLE)."""
#     msg = str(e)
#     return "503" in msg or "UNAVAILABLE" in msg


# def ask_gemini(prompt, conversation_history=None):

#     history = ""
#     if conversation_history:
#         for msg in conversation_history:
#             history += f"{msg['role']}: {msg['content']}\n"

#     full_prompt = history + "\nuser: " + prompt if history else prompt

#     last_error = None

#     for model_name in MODELS_TO_TRY:

#         for attempt in range(3):

#             try:
#                 print(f"[Gemini] Trying {model_name} (attempt {attempt + 1}/3)")

#                 response = client.models.generate_content(
#                     model=model_name,
#                     contents=full_prompt
#                 )

#                 if response and response.text:
#                     print(f"[Gemini] Success using {model_name}")
#                     return response.text

#             except Exception as e:
#                 last_error = e
#                 print(f"[Gemini] {model_name} attempt {attempt + 1}/3 failed: {e}")

#                 if _is_quota_error(e):
#                     # Hard quota limit — retrying same model won't help, skip to next
#                     print(f"[Gemini] {model_name} quota exhausted, skipping to next model.")
#                     break

#                 if _is_overload_error(e):
#                     # Temporary overload — wait a bit longer before retrying
#                     wait = RETRY_DELAY * (attempt + 1)
#                     print(f"[Gemini] {model_name} overloaded, waiting {wait}s before retry...")
#                     time.sleep(wait)
#                     continue

#                 # Unknown error — standard wait
#                 time.sleep(RETRY_DELAY)

#     raise Exception(f"All Gemini models failed. Last error: {last_error}")