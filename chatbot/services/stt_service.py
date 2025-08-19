import speech_recognition as sr

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
