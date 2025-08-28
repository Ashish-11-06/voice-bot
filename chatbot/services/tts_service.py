import base64
import time
import os
import requests
import emoji
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def clean_text(text: str) -> str:
    """
    Remove emojis and asterisks from the text.
    """
    if not text:
        return ""
        
    text = emoji.replace_emoji(text, replace='')  # remove emojis
    text = text.replace('*', '')  # remove asterisks
    return text.strip()

async def generate_voice_response(text: str, sid: str = "", voice: str = "onyx", model: str = "tts-1") -> str:
    """
    Generate voice using OpenAI TTS API. Returns base64-encoded WAV audio.
    """
    if not text:
        logger.warning(f"Empty text for TTS for {sid}")
        return ""
        
    start_time = time.time()
    cleaned_text = clean_text(text)
    
    if not cleaned_text:
        logger.warning(f"Text empty after cleaning for {sid}")
        return ""
        
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY not set in environment")
        return ""

    try:
        url = "https://api.openai.com/v1/audio/speech"
        headers = {
            "Authorization": f"Bearer {api_key}",
        }
        payload = {
            "model": model,
            "input": cleaned_text,
            "voice": voice,
            "response_format": "wav"
        }
        
        # Set timeout and make request
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code != 200:
            logger.error(f"OpenAI TTS failed: {response.status_code} - {response.text}")
            return ""

        wav_bytes = response.content
        end_time = time.time()
        
        logger.debug(f"TTS for {sid} took {end_time - start_time:.3f} seconds, text: '{cleaned_text[:50]}...'")
        return base64.b64encode(wav_bytes).decode("utf-8")
        
    except requests.exceptions.Timeout:
        logger.error(f"TTS request timed out for {sid}")
        return ""
    except requests.exceptions.RequestException as e:
        logger.error(f"TTS request failed for {sid}: {e}")
        return ""
    except Exception as e:
        logger.error(f"Unexpected error in TTS for {sid}: {e}")
        return ""