# /stt_service.py
import base64
import wave
import tempfile
import os
import speech_recognition as sr
import time
import re

recognizer = sr.Recognizer()

def transcribe_pcm16_audio(audio_data: bytes, sample_rate: int = 16000) -> str:
    """
    Convert raw PCM16 audio bytes to text using Google Web Speech API.
    Returns recognized text or error message.
    """
    if not audio_data:
        return ""

    tmp_path = None
    start_time = time.time()
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

            # Check if text has any alphabetic letters
            if not text.strip():
                return "[Heard Noise]"  # empty text
            elif not re.search(r'[a-zA-Z]', text):
                return "[Unrecognized Speech]"  # some sound detected but cannot recognize
            return text

        except sr.UnknownValueError:
            return "[Unrecognized Speech]"
        except sr.RequestError:
            return "[STT Service Error]"

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        end_time = time.time()
        print(f"[STT] Time taken: {end_time - start_time:.3f} seconds")
        
        

class STTSession:
    def __init__(self):
        self.recognizer = sr.Recognizer()

    def transcribe_audio(self, audio_bytes: bytes) -> str:
        """Convert raw audio bytes into text with timing info."""
        start_time = time.time()
        with sr.AudioFile(audio_bytes) as source:
            audio = self.recognizer.record(source)
        try:
            text = self.recognizer.recognize_google(audio)
        except sr.UnknownValueError:
            text = "[Unrecognized Speech]"
        except sr.RequestError:
            text = "[STT Service Error]"
        finally:
            end_time = time.time()
            print(f"[STTSession] Time taken: {end_time - start_time:.3f} seconds")
        return text

class STTSession:
    def __init__(self):
        self.recognizer = sr.Recognizer()

    def transcribe_audio(self, audio_bytes: bytes) -> str:
        """Convert raw audio bytes into text."""
        with sr.AudioFile(audio_bytes) as source:
            audio = self.recognizer.record(source)
        try:
            text = self.recognizer.recognize_google(audio)
            return text
        except sr.UnknownValueError:
            return "[Unrecognized Speech]"
        except sr.RequestError:
            return "[STT Service Error]"
