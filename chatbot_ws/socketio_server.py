# chatbot_ws/socketio_server.py
import os
import django
import socketio
import json
import tempfile
import base64
import wave

from chatbot.services.chatbot_core import process_text_message
from .Kids_bot import MultiLanguageBalSamagamChatbot
from chatbot.services.stt_service import transcribe_pcm16_audio
from .blood_donation import BloodDonationChatbot

# Django setup
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "chatbot_project.settings")
django.setup()


# Socket.IO ASGI app
sio = socketio.AsyncServer(cors_allowed_origins="*", async_mode="asgi")
app = socketio.ASGIApp(sio)

# Instantiate the chatbot
# chatbot = MultiLanguageBalSamagamChatbot()
chatbot = BloodDonationChatbot()
# blood_donation_chatbot = BloodDonationChatbot()

# Store audio buffers per client
audio_buffers = {}  # sid -> bytearray


@sio.event
async def connect(sid, environ):
    print(f"Client {sid} connected")
    audio_buffers[sid] = bytearray()
    await sio.emit("server_info", {"msg": "connected", "sample_rate": 16000}, to=sid)


@sio.event
async def disconnect(sid):
    print(f"Client {sid} disconnected")
    audio_buffers.pop(sid, None)


@sio.on("message")
async def handle_message(sid, data):
    """
    Handle plain text messages from client.
    """
    user_text = (data or {}).get("text", "")
    if not user_text:
        return
    
    await sio.emit("bot_thinking", {"status": "thinking"}, to=sid)
    
    # Use chatbot.chat (sync) before process_text_message (async)
    response = chatbot.chat(sid, user_text)
    result = await process_text_message(response, sid)
    await sio.emit("bot_reply", result, to=sid)


@sio.on("voice_chunk")
async def handle_voice_chunk(sid, data):
    """
    Receive raw PCM16 audio (from ArrayBuffer) and buffer it.
    """
    if sid not in audio_buffers or data is None:
        return

    # Case 1: frontend sent ArrayBuffer → arrives as list[int]
    if isinstance(data, list):
        try:
            data = bytes(bytearray(data))
        except Exception:
            return

    # Case 2: base64 string
    elif isinstance(data, str):
        try:
            data = base64.b64decode(data)
        except Exception:
            return

    # Case 3: already bytes
    elif not isinstance(data, (bytes, bytearray)):
        return

    audio_buffers[sid].extend(data)


@sio.on("end_voice")
async def handle_end_voice(sid):
    """
    Finalize STT using speech_recognition.
    """
    if sid not in audio_buffers:
        return

    audio_data = audio_buffers[sid]
    audio_buffers[sid] = bytearray()  # reset buffer

    text = transcribe_pcm16_audio(audio_data)

    if text and not text.startswith("["):
        print(f"[User {sid}]: {text}")
        await sio.emit("bot_thinking", {"status": "thinking", "user_text": text}, to=sid)
        response = chatbot.chat(sid, text)
        bot_result = await process_text_message(response, sid)
        await sio.emit("bot_reply", bot_result, to=sid)
    else:
        await sio.emit("partial_text", {"text": text}, to=sid)
        
