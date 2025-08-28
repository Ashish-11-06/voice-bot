import logging
from chatbot.services.tts_service import generate_voice_response

logger = logging.getLogger(__name__)

async def process_text_message(user_text: str, sid: str):
    """
    Process a text input -> return recognized user text and bot reply with audio.
    """
    try:
        if not user_text or not user_text.strip():
            logger.warning(f"Empty user text from {sid}")
            return {
                "user_text": "",
                "bot_text": "Please say something!",
                "bot_audio": ""
            }

        # In this simplified version, we just echo back with TTS
        # In a real implementation, you would call your chatbot here
        reply_text = f"I heard: {user_text}"
        b64_wav = await generate_voice_response(reply_text, sid)
        
        return {
            "user_text": user_text,
            "bot_text": reply_text,
            "bot_audio": b64_wav,
        }
        
    except Exception as e:
        logger.error(f"Error processing text message: {e}")
        return {
            "user_text": user_text,
            "bot_text": "Sorry, I encountered an error processing your message.",
            "bot_audio": ""
        }