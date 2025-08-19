# chatbot/services/tts_service.py
import base64
import os
import tempfile
from gtts import gTTS

async def generate_voice_response(text: str) -> str:
    """
    Generate speech from text using gTTS and return base64 encoded MP3.
    """
    # Create temporary file for MP3
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as fp:
        tts = gTTS(text=text, lang='en')
        tts.save(fp.name)

        # Read and encode audio
        with open(fp.name, "rb") as audio_file:
            audio_data = audio_file.read()

        # Cleanup
        os.unlink(fp.name)

    return base64.b64encode(audio_data).decode("utf-8")
