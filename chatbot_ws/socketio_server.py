# Add at the top of socketio_server.py and other main files
from .logger_config import setup_logging
setup_logging()
import os
import django
import socketio
import json
import tempfile
import base64
import wave
import logging
import asyncio
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Django setup
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "chatbot_project.settings")
django.setup()

# Import your chatbot
from .Kids_bot import MultiLanguageBalSamagamChatbot
from .stt_service import transcribe_pcm16_audio
from chatbot.services.tts_service import generate_voice_response

# Import local whisper for fast transcription
try:
    from faster_whisper import WhisperModel
    local_model = WhisperModel("tiny", device="cpu", compute_type="int8")
    HAS_LOCAL_WHISPER = True
except ImportError:
    logger.warning("faster_whisper not available, using OpenAI STT only")
    HAS_LOCAL_WHISPER = False

# Socket.IO ASGI app
sio = socketio.AsyncServer(
    cors_allowed_origins="*", 
    async_mode="asgi",
    logger=True,
    engineio_logger=True
)
app = socketio.ASGIApp(sio, socketio_path="socket.io")

# Instantiate the chatbot
chatbot = MultiLanguageBalSamagamChatbot()

# Store audio buffers per client
audio_buffers = {}

def quick_local_transcribe(audio_bytes: bytes, sample_rate: int = 16000) -> str:
    """Local transcription using faster_whisper"""
    if not HAS_LOCAL_WHISPER:
        return ""
        
    try:
        import numpy as np
        import io
        
        # Convert PCM16 → numpy float32
        audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        segments, _ = local_model.transcribe(audio, beam_size=1, language="en")
        return " ".join([seg.text for seg in segments]).strip()
    except Exception as e:
        logger.error(f"Local transcription failed: {e}")
        return ""

@sio.event
async def connect(sid, environ):
    """Handle client connection"""
    logger.info(f"Client {sid} connected")
    audio_buffers[sid] = bytearray()
    await sio.emit("server_info", {
        "msg": "connected", 
        "sample_rate": 16000,
        "status": "ready"
    }, to=sid)

@sio.event
async def disconnect(sid):
    """Handle client disconnection"""
    logger.info(f"Client {sid} disconnected")
    if sid in audio_buffers:
        del audio_buffers[sid]

@sio.on("message")
async def handle_message(sid, data):
    """
    Handle plain text messages from client.
    """
    try:
        user_text = (data or {}).get("text", "").strip()
        if not user_text:
            logger.warning(f"Empty text message from {sid}")
            return
        
        logger.info(f"Text message from {sid}: {user_text}")
        await sio.emit("bot_thinking", {"status": "thinking"}, to=sid)
        
        # Process the message
        response = chatbot.chat(sid, user_text)
        
        # Generate voice response
        result = await generate_voice_response(response, sid)
        
        await sio.emit("bot_reply", {
            "user_text": user_text,
            "bot_text": response,
            "bot_audio": result
        }, to=sid)
        
    except Exception as e:
        logger.error(f"Error handling text message: {e}")
        await sio.emit("error", {"message": "Failed to process message"}, to=sid)

@sio.on("voice_chunk")
async def handle_voice_chunk(sid, data):
    """
    Receive raw PCM16 audio and buffer it.
    """
    try:
        if sid not in audio_buffers:
            audio_buffers[sid] = bytearray()

        # Handle different data formats
        if isinstance(data, list):
            data = bytes(bytearray(data))
        elif isinstance(data, str):
            data = base64.b64decode(data)
        elif not isinstance(data, (bytes, bytearray)):
            logger.warning(f"Invalid data type from {sid}: {type(data)}")
            return

        # Limit buffer size to prevent memory issues (10 seconds of audio)
        max_size = 16000 * 2 * 10  # 10 seconds of 16kHz 16-bit audio
        if len(audio_buffers[sid]) + len(data) > max_size:
            logger.warning(f"Audio buffer overflow for {sid}, truncating")
            audio_buffers[sid] = audio_buffers[sid][-max_size//2:]  # Keep last 5 seconds

        audio_buffers[sid].extend(data)
        
    except Exception as e:
        logger.error(f"Error handling voice chunk: {e}")

@sio.on("end_voice")
async def handle_end_voice(sid):
    """
    Finalize STT using Whisper, then reply with TTS audio.
    """
    try:
        if sid not in audio_buffers or not audio_buffers[sid]:
            logger.warning(f"No audio data for {sid}")
            await sio.emit("partial_text", {"text": "[No audio detected]"}, to=sid)
            return

        audio_data = bytes(audio_buffers[sid])
        audio_buffers[sid] = bytearray()  # reset buffer
        
        logger.debug(f"Processing audio from {sid}, size: {len(audio_data)} bytes")

        # First try local transcription for speed
        local_text = ""
        if HAS_LOCAL_WHISPER:
            local_text = quick_local_transcribe(audio_data)
            logger.debug(f"Local transcription: {local_text}")
            
            # If local transcription is good, use it
            if local_text and len(local_text.strip()) > 3 and local_text.strip() not in ["[unrecognized speech]", "[silence]", "[noise]"]:
                text = local_text
                logger.info(f"Using local transcription for {sid}: {text}")
            else:
                # Fall back to OpenAI STT
                text = transcribe_pcm16_audio(audio_data)
        else:
            # Use OpenAI STT directly
            text = transcribe_pcm16_audio(audio_data)

        if not text or text.strip() == "":
            logger.warning(f"No speech recognized for {sid}")
            await sio.emit("partial_text", {"text": "[Unrecognized Speech]"}, to=sid)
            return

        logger.info(f"User {sid} said: {text}")
        await sio.emit("partial_text", {"text": text}, to=sid)
        await sio.emit("bot_thinking", {"status": "thinking", "user_text": text}, to=sid)

        # Get bot response
        response = chatbot.chat(sid, text)
        
        # Generate voice response
        bot_audio = await generate_voice_response(response, sid)
        
        # Send response
        await sio.emit("bot_reply", {
            "user_text": text,
            "bot_text": response,
            "bot_audio": bot_audio
        }, to=sid)

    except Exception as e:
        logger.error(f"Error in handle_end_voice: {e}")
        await sio.emit("error", {"message": "Failed to process audio"}, to=sid)

# Health check endpoint
@sio.on("ping")
async def handle_ping(sid, data):
    """Health check endpoint"""
    await sio.emit("pong", {"timestamp": datetime.now().isoformat()}, to=sid)