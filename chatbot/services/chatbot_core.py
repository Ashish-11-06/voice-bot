# chatbot/services/chatbot_core.py
from chatbot.services.tts_service import generate_voice_response

async def process_text_message(user_text: str):
    """
    Process a text input -> return recognized user text and bot reply with audio.
    """
    reply_text = f"you just said {user_text}"
    b64_wav = await generate_voice_response(reply_text)  # 16kHz mono WAV -> base64
    return {
        "user_text": user_text,
        "bot_text": reply_text,
        "bot_audio": b64_wav,
    }
