# chatbot_ws/stt_service.py
import base64
import wave
import tempfile
import os
import speech_recognition as sr

recognizer = sr.Recognizer()


def transcribe_pcm16_audio(audio_data: bytes, sample_rate: int = 16000) -> str:
    """
    Convert raw PCM16 audio bytes to text using Google Web Speech API.
    Returns recognized text or error message.
    """
    if not audio_data:
        return ""

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
            text = recognizer.recognize_google(audio)
        except sr.UnknownValueError:
            text = "[Unrecognized Speech]"
        except sr.RequestError:
            text = "[STT Service Error]"

        return text

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)