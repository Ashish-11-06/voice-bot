import os
import requests
import io
import wave
import time
import logging

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

def transcribe_pcm16_audio(
    audio_data: bytes,
    sample_rate: int = 16000,
    model: str = "gpt-4o-mini-transcribe",
    retries: int = 2,
    timeout: int = 30
) -> str:
    """
    Convert raw PCM16 audio bytes to text using OpenAI STT API.
    """
    if not audio_data:
        logger.warning("Empty audio data for transcription")
        return ""

    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not set in environment")
        return "[STT Error] API key not configured"

    try:
        # Write PCM16 into an in-memory WAV
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # PCM16 = 2 bytes
            wf.setframerate(sample_rate)
            wf.writeframes(audio_data)
        buffer.seek(0)

        url = "https://api.openai.com/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
        files = {"file": ("audio.wav", buffer, "audio/wav")}
        data = {"model": model, "response_format": "json"}

        for attempt in range(retries + 1):
            try:
                resp = requests.post(url, headers=headers, files=files, data=data, timeout=timeout)
                
                if resp.status_code == 200:
                    result = resp.json().get("text", "")
                    logger.debug(f"STT successful: {result}")
                    return result
                else:
                    err = resp.json().get("error", {}).get("message", resp.text)
                    logger.warning(f"STT attempt {attempt+1} failed: {resp.status_code} - {err}")
                    
                    if attempt < retries:
                        time.sleep(1)  # backoff
                        continue
                    
                    return f"[STT Error {resp.status_code}] {err}"
                    
            except requests.exceptions.Timeout:
                logger.warning(f"STT attempt {attempt+1} timed out")
                if attempt < retries:
                    continue
                return "[STT Error] Request timed out"
                
            except Exception as e:
                logger.error(f"STT attempt {attempt+1} exception: {e}")
                if attempt < retries:
                    time.sleep(1)
                    continue
                return f"[STT Exception] {str(e)}"

        return ""  # fallback
        
    except Exception as e:
        logger.error(f"Unexpected error in STT: {e}")
        return f"[STT Error] {str(e)}"