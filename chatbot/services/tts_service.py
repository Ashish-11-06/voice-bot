# chatbot/services/tts_service.py
import base64
import io
from gtts import gTTS
from pydub import AudioSegment

async def generate_voice_response(text: str) -> str:
    """
    gTTS -> MP3 (memory) -> WAV (PCM16 mono 16kHz) -> base64
    """
    mp3_fp = io.BytesIO()
    tts = gTTS(text=text, lang="en")
    tts.write_to_fp(mp3_fp)
    mp3_fp.seek(0)

    audio = AudioSegment.from_file(mp3_fp, format="mp3")
    audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)

    wav_fp = io.BytesIO()
    audio.export(wav_fp, format="wav")
    wav_fp.seek(0)

    return base64.b64encode(wav_fp.read()).decode("utf-8")
