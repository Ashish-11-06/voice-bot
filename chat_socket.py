import base64
import json
import socketio
import numpy as np

from vosk import Model, KaldiRecognizer
from chatbot.services.tts_service import generate_voice_response

# Socket.IO server
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
app = socketio.ASGIApp(sio)

# Vosk setup
VOSK_MODEL_PATH = "/home/ashish/PP/bot/voice_chatbot/chatbot_project/vosk-model-small-en-us-0.15/vosk-model-small-en-us-0.15"
vosk_model = Model(VOSK_MODEL_PATH)
recognizer = KaldiRecognizer(vosk_model, 16000)
recognizer.SetWords(True)

@sio.event
async def connect(sid, environ):
    print("🔗 Client connected:", sid)
    await sio.emit("info", {"msg": "Connected to STT/TTS bot"}, to=sid)

@sio.on("audio_chunk")
async def audio_chunk(sid, data):
    """
    Receive audio chunks from client (base64 PCM16 at 16kHz mono).
    """
    pcm_bytes = base64.b64decode(data)
    if recognizer.AcceptWaveform(pcm_bytes):
        result = json.loads(recognizer.Result())
        text = (result.get("text") or "").strip()
        if text:
            # Send STT result
            await sio.emit("stt_text", {"user_text": text}, to=sid)

            # Generate TTS
            reply_text = f"you just said {text}"
            await sio.emit("bot_text", {"bot_text": reply_text}, to=sid)

            b64_wav = await generate_voice_response(reply_text)
            await sio.emit("tts_audio", {"audio": b64_wav}, to=sid)

@sio.event
async def disconnect(sid):
    print("❌ Client disconnected:", sid)
