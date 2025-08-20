# chatbot_ws/socketio_server.py
import os
import django
import socketio
import json
from vosk import Model, KaldiRecognizer

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "chatbot_project.settings")
django.setup()

# Socket.IO ASGI app
sio = socketio.AsyncServer(cors_allowed_origins="*", async_mode="asgi")
app = socketio.ASGIApp(sio)

from chatbot.services.chatbot_core import process_text_message

# ---------------------------
# Load vosk model once globally
# ---------------------------
VOSK_MODEL_PATH = "/home/ashish/PP/bot/voice_chatbot/chatbot_project/vosk-model-small-en-us-0.15/vosk-model-small-en-us-0.15"
model = Model(VOSK_MODEL_PATH)

# Store a recognizer per client
recognizers = {}  # sid -> KaldiRecognizer(16000)

@sio.event
async def connect(sid, environ):
    print(f"Client {sid} connected")
    recognizers[sid] = KaldiRecognizer(model, 16000)
    await sio.emit("server_info", {"msg": "connected", "sample_rate": 16000}, to=sid)

@sio.event
async def disconnect(sid):
    print(f"Client {sid} disconnected")
    recognizers.pop(sid, None)

@sio.on("message")
async def handle_message(sid, data):
    """
    Optional: plain text message → TTS echo reply
    """
    user_text = (data or {}).get("text", "")
    if not user_text:
        return
    result = await process_text_message(user_text)
    await sio.emit("bot_reply", result, to=sid)

@sio.on("voice_chunk")
async def handle_voice_chunk(sid, data):
    """
    Receive a *single* utterance as raw PCM16 bytes @16k from frontend.
    We call FinalResult() to flush stable text for this chunk,
    then synthesize TTS and push back to the client.
    """
    if sid not in recognizers or not data:
        return

    rec = recognizers[sid]

    # Data should be raw bytes (ArrayBuffer from frontend)
    if not isinstance(data, (bytes, bytearray)):
        # If you see dict with {_placeholder: true, num: 0}, your frontend
        # is not sending ArrayBuffer directly. Fix frontend.
        return

    # Feed the chunk and flush
    try:
        rec.AcceptWaveform(data)   # feed
        result_json = rec.FinalResult()  # flush the chunk
        result = json.loads(result_json or "{}")
        text = (result.get("text") or "").strip()
        if text:
            print(f"[User {sid}]: {text}")
            bot_result = await process_text_message(text)
            await sio.emit("bot_reply", bot_result, to=sid)
        else:
            await sio.emit("partial_text", {"text": ""}, to=sid)
    except Exception as e:
        await sio.emit("server_info", {"error": f"STT error: {e}"}, to=sid)
