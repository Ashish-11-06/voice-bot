import os
import django
import socketio
import json
import base64
import wave
import tempfile
import time
import re
import speech_recognition as sr
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from chatbot.services.chatbot_core import process_text_message
from .balsamagam import BalSamagamChatbot
from .BloodDonation import blood_donation
from GMTT import GMTT

# Django setup
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "chatbot_project.settings")
django.setup()

# Socket.IO ASGI app
sio = socketio.AsyncServer(cors_allowed_origins="*", async_mode="asgi")
app = socketio.ASGIApp(sio, socketio_path="/socket.io")

# --- ✅ Bot registry ---
BOT_REGISTRY = {
    "balsamagam": BalSamagamChatbot(),
    "blood_donation": blood_donation.BloodDonationChatbot(),
    "gmtt": GMTT.GMTTChatbot(),
}

# Store audio buffers per client: {"full": bytearray, "chunk": bytearray}
audio_buffers = {}

# Store bot choice per client
client_bots = {}

# Init recognizer
recognizer = sr.Recognizer()

# Rolling window size for partial STT (~1 sec at 16kHz PCM16)
CHUNK_WINDOW_SIZE = 16000 * 2  # 1 second = 16000 samples * 2 bytes


def get_client_bot(sid):
    """Return the assigned bot for a client, default to balsamagam."""
    bot_name = client_bots.get(sid, "balsamagam")
    return BOT_REGISTRY[bot_name]


def transcribe_pcm16_audio(audio_data: bytes, sample_rate: int = 16000, partial: bool = False) -> str:
    if not audio_data:
        return ""

    tmp_path = None
    start_time = time.time()
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmpfile:
            with wave.open(tmpfile, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # PCM16 = 2 bytes
                wf.setframerate(sample_rate)
                wf.writeframes(audio_data)
            tmp_path = tmpfile.name

        with sr.AudioFile(tmp_path) as source:
            audio = recognizer.record(source)

        try:
            text = recognizer.recognize_google(audio)

            if not text.strip():
                return "[Heard Noise]"
            elif not re.search(r"[a-zA-Z]", text):
                return "[Unrecognized Speech]"
            return text

        except sr.UnknownValueError:
            return "[Unrecognized Speech]" if not partial else ""
        except sr.RequestError:
            return "[STT Service Error]"

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        end_time = time.time()
        print(f"[STT] Time taken: {end_time - start_time:.3f} seconds")


# ----------------- Socket Events -----------------

@sio.event
async def connect(sid, environ):
    print(f"Client {sid} connected")
    audio_buffers[sid] = {"full": bytearray(), "chunk": bytearray()}
    client_bots[sid] = "balsamagam"  # default bot
    await sio.emit("server_info", {"msg": "connected", "sample_rate": 16000}, to=sid)


@sio.event
async def disconnect(sid):
    print(f"Client {sid} disconnected")
    audio_buffers.pop(sid, None)
    client_bots.pop(sid, None)


@sio.on("select_bot")
async def handle_select_bot(sid, data):
    bot_name = (data or {}).get("bot", "balsamagam")
    if bot_name in BOT_REGISTRY:
        client_bots[sid] = bot_name
        print(f"Client {sid} switched to bot: {bot_name}")
        await sio.emit("bot_selected", {"bot": bot_name}, to=sid)
    else:
        await sio.emit("bot_error", {"error": "Invalid bot selected"}, to=sid)


@sio.on("message")
async def handle_message(sid, data):
    user_text = (data or {}).get("text", "")
    if not user_text:
        return

    await sio.emit("bot_thinking", {"status": "thinking"}, to=sid)

    bot = get_client_bot(sid)
    response = bot.chat(sid, user_text)
    result = await process_text_message(response, sid)
    await sio.emit("bot_reply", result, to=sid)


@sio.on("voice_chunk")
async def handle_voice_chunk(sid, data):
    if sid not in audio_buffers or data is None:
        return

    if isinstance(data, list):
        try:
            data = bytes(bytearray(data))
        except Exception:
            return
    elif isinstance(data, str):
        try:
            data = base64.b64decode(data)
        except Exception:
            return
    elif not isinstance(data, (bytes, bytearray)):
        return

    audio_buffers[sid]["full"].extend(data)

    buf = audio_buffers[sid]["chunk"]
    buf.extend(data)

    if len(buf) > CHUNK_WINDOW_SIZE:
        buf[:] = buf[-CHUNK_WINDOW_SIZE:]

    if len(buf) > 10000:
        partial_text = transcribe_pcm16_audio(buf, partial=True)
        if partial_text:
            print(f"[Partial STT {sid}]: {partial_text}")
            await sio.emit("partial_text", {"text": partial_text}, to=sid)


@sio.on("end_voice")
async def handle_end_voice(sid):
    if sid not in audio_buffers:
        return

    full_data = audio_buffers[sid]["full"]
    audio_buffers[sid] = {"full": bytearray(), "chunk": bytearray()}

    text = transcribe_pcm16_audio(full_data)

    if text and not text.startswith("["):
        print(f"[User {sid}]: {text}")
        lower_text = text.lower()

        # --- ✅ Robot movement logic ---
        if re.search(r"\b(hello|hey|hii|hi)\b", lower_text):
            action = "shake_hand"
        elif re.search(r"\b(dhan nirankar ji|dhhan nirankar jii|dhaan nirankar ji|namaskar|namste|namaste)\b", lower_text):
            action = "namaste"
        else:
            action = "hand_movement"

        print(f"[Immediate Robot Command]: {action}")
        await sio.emit("robot_signal", {"action": action}, to=sid)
        await sio.emit("bot_thinking", {"status": "thinking", "user_text": text}, to=sid)

        bot = get_client_bot(sid)
        response = bot.chat(sid, text)
        bot_result = await process_text_message(response, sid)
        await sio.emit("bot_reply", bot_result, to=sid)
    else:
        await sio.emit("partial_text", {"text": text}, to=sid)
