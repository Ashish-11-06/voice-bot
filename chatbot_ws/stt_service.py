import os
import requests
import io
import wave
import time
import logging
import tempfile
import speech_recognition as sr

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
recognizer = sr.Recognizer()

def transcribe_pcm16_audio(
    audio_data: bytes,
    sample_rate: int = 16000,
    model: str = "gpt-4o-mini-transcribe",
    retries: int = 1,  # Reduced retries for faster fallback
    timeout: int = 10  # Reduced timeout for faster fallback
) -> str:
    """
    Convert raw PCM16 audio bytes to text using OpenAI STT API first,
    then fall back to Google Web Speech API if OpenAI fails.
    """
    if not audio_data:
        logger.warning("Empty audio data for transcription")
        return ""

    # First try OpenAI STT
    openai_result = _transcribe_with_openai(
        audio_data, sample_rate, model, retries, timeout
    )

    # Check if OpenAI returned an error that should trigger fallback
    if _should_fallback_to_google(openai_result):
        logger.warning(f"OpenAI STT failed with: {openai_result}, trying Google STT...")
        # Use Google STT with silence/noise thresholding
        google_result = _transcribe_with_google_with_threshold(audio_data, sample_rate)
        if google_result and not _is_error_result(google_result):
            logger.debug(f"Google STT successful: {google_result}")
            return google_result
        else:
            logger.warning(f"Google STT also failed: {google_result}")
            return google_result  # Return Google's error message

    # If OpenAI succeeded or returned a non-fallback error, return its result
    return openai_result


def _transcribe_with_google_with_threshold(audio_data: bytes, sample_rate: int) -> str:
    """Google STT with silence/noise thresholding"""
    tmp_path = None
    try:
        # Save audio temporarily as WAV (16k mono PCM16)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmpfile:
            with wave.open(tmpfile, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # PCM16 = 2 bytes
                wf.setframerate(sample_rate)
                wf.writeframes(audio_data)
            tmp_path = tmpfile.name

        # Recognize speech with silence/noise thresholding
        with sr.AudioFile(tmp_path) as source:
            # Set thresholds for silence and noise
            recognizer.energy_threshold = 300  # adjust as needed (default 300)
            recognizer.dynamic_energy_threshold = True  # let recognizer adapt to noise
            audio = recognizer.record(source)

        try:
            text = recognizer.recognize_google(audio).strip()
            if not text:
                return "[Unrecognized Speech]"
            return text
        except sr.UnknownValueError:
            return "[Unrecognized Speech]"
        except sr.RequestError as e:
            logger.error(f"Google STT service error: {e}")
            return "[STT Service Error]"
        except Exception as e:
            logger.error(f"Google STT unexpected error: {e}")
            return "[STT Service Error]"

    except Exception as e:
        logger.error(f"Google STT processing error: {e}")
        return "[STT Service Error]"
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except:
                pass

def _should_fallback_to_google(result: str) -> bool:
    """Check if the result indicates we should fall back to Google STT"""
    if not result:
        return True
    
    # Fallback for rate limits, format errors, and other API issues
    error_patterns = [
        '[STT Error 429]', 
        '[STT Error 400]',
        '[STT Error] Request timed out',
        '[STT Error] API key not configured',
        '[STT Exception]',
        '[Unrecognized Speech]'  # OpenAI returned empty text
    ]
    
    return any(pattern in result for pattern in error_patterns)

def _is_error_result(result: str) -> bool:
    """Check if the result is an error message"""
    if not result:
        return True
    
    error_patterns = [
        '[STT Error',
        '[Unrecognized Speech]',
        '[STT Service Error]'
    ]
    
    return any(pattern in result for pattern in error_patterns)

def _transcribe_with_openai(
    audio_data: bytes,
    sample_rate: int,
    model: str,
    retries: int,
    timeout: int
) -> str:
    """Internal function for OpenAI STT transcription"""
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
                    result = resp.json().get("text", "").strip()
                    if not result:
                        return "[Unrecognized Speech]"
                    return result
                else:
                    err = resp.json().get("error", {}).get("message", resp.text)
                    logger.warning(f"OpenAI STT attempt {attempt+1} failed: {resp.status_code} - {err}")
                    
                    # Return the error message (will trigger fallback in main function)
                    return f"[STT Error {resp.status_code}] {err}"
                    
            except requests.exceptions.Timeout:
                logger.warning(f"OpenAI STT attempt {attempt+1} timed out")
                return "[STT Error] Request timed out"
                
            except Exception as e:
                logger.error(f"OpenAI STT attempt {attempt+1} exception: {e}")
                return f"[STT Exception] {str(e)}"

        return "[STT Error] All attempts failed"
        
    except Exception as e:
        logger.error(f"Unexpected error in OpenAI STT: {e}")
        return f"[STT Error] {str(e)}"

def _transcribe_with_google(audio_data: bytes, sample_rate: int) -> str:
    """Internal function for Google STT transcription"""
    tmp_path = None
    try:
        # Save audio temporarily as WAV (16k mono PCM16)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmpfile:
            with wave.open(tmpfile, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # PCM16 = 2 bytes
                wf.setframerate(sample_rate)
                wf.writeframes(audio_data)
            tmp_path = tmpfile.name

        # Recognize speech
        with sr.AudioFile(tmp_path) as source:
            audio = recognizer.record(source)

        try:
            text = recognizer.recognize_google(audio).strip()
            if not text:
                return "[Unrecognized Speech]"
            return text
        except sr.UnknownValueError:
            return "[Unrecognized Speech]"
        except sr.RequestError as e:
            logger.error(f"Google STT service error: {e}")
            return "[STT Service Error]"
        except Exception as e:
            logger.error(f"Google STT unexpected error: {e}")
            return "[STT Service Error]"

    except Exception as e:
        logger.error(f"Google STT processing error: {e}")
        return "[STT Service Error]"
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except:
                pass