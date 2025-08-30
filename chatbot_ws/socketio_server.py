from .logger_config import setup_logging
setup_logging()
import os
import django
import socketio
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "chatbot_project.settings")
django.setup()

from .Kids_bot import MultiLanguageBalSamagamChatbot
from .stt_service import transcribe_pcm16_audio
from chatbot.services.tts_service import generate_voice_response
from chatbot.services.chatbot_core import process_text_message

# Socket.IO setup
sio = socketio.AsyncServer(
    cors_allowed_origins="*", 
    async_mode="asgi",
    logger=True
)
app = socketio.ASGIApp(sio)

chatbot = MultiLanguageBalSamagamChatbot()
audio_buffers = {}

@sio.event
async def connect(sid, environ):
    """Handle client connection"""
    print("connected")
    audio_buffers[sid] = bytearray()
    # last_user_messages[sid] = ""
    await sio.emit("server_info", {
        "msg": "connected", 
        "sample_rate": 16000,
        "status": "ready"
    }, to=sid)

@sio.event
async def disconnect(sid):
    """Handle client disconnection"""
    logger.info(f"Client {sid} disconnected")
    audio_buffers.pop(sid, None)

# @sio.on("message")
# async def handle_message(sid, data):
#     """Handle text messages from client"""
#     try:
#         user_text = (data or {}).get("text", "").strip()
#         await sio.emit("bot_thinking", {"status": "thinking"}, to=sid)
        
#         # Process message
#         chatbot_response = chatbot.chat(sid, user_text)
#         processed_result = await process_text_message(chatbot_response, sid)
        
#         bot_text = processed_result.get("text", chatbot_response)
#         bot_audio = processed_result.get("audio") or await generate_voice_response(bot_text, sid)
        
#         await sio.emit("bot_reply", {
#             "bot_text": bot_text,
#             "bot_audio": bot_audio
#         }, to=sid)
        
#     except Exception as e:
#         logger.error(f"Error handling text message: {e}")
#         await sio.emit("error", {"message": "Failed to process message"}, to=sid)

@sio.on("voice_chunk")
async def handle_voice_chunk(sid, data):
    """Buffer incoming audio chunks"""
    try:
        if sid not in audio_buffers:
            audio_buffers[sid] = bytearray()

        # Convert different data formats to bytes
        if isinstance(data, list):
            data = bytes(data)
        elif isinstance(data, str):
            data = bytes.fromhex(data) if all(c in '0123456789ABCDEFabcdef' for c in data) else data.encode()
        
        if isinstance(data, (bytes, bytearray)):
            # Limit buffer size to prevent memory issues
            max_size = 16000 * 2 * 10  # 10 seconds of audio
            if len(audio_buffers[sid]) + len(data) > max_size:
                audio_buffers[sid] = audio_buffers[sid][-max_size//2:]
            audio_buffers[sid].extend(data)
            
    except Exception as e:
        logger.error(f"Error handling voice chunk: {e}")

@sio.on("end_voice")
async def handle_end_voice(sid):
    """Process completed audio and generate response"""
    try:
        if sid not in audio_buffers or not audio_buffers[sid]:
            await sio.emit("partial_text", {"text": "[No audio detected]"}, to=sid)
            return

        audio_data = bytes(audio_buffers[sid])
        audio_buffers[sid] = bytearray()
        


        # Transcribe audio and get which model was used
        text, stt_model = transcribe_pcm16_audio(audio_data)

        # Print and emit the recognized text (message to the model) and which STT model was used
        print(f"Message to model: {text} (STT model: {stt_model})")
        await sio.emit("message_to_model", {"text": text, "stt_model": stt_model}, to=sid)

        # If both STT fail, text will be empty or an error string, do not proceed
        if not text or text.strip() == "" or text in ["[Unrecognized Speech]", "[STT Service Error]", "[STT Error] API key not configured"]:
            await sio.emit("partial_text", {"text": text if text else "[Unrecognized Speech]"}, to=sid)
            await sio.emit("error", {"message": "Speech recognition failed. Please try again."}, to=sid)
            print(f"[STT DEBUG] Not passing to model. Reason: {text}")
            return

        await sio.emit("partial_text", {"text": text}, to=sid)
        await sio.emit("bot_thinking", {"status": "thinking", "user_text": text}, to=sid)

        # Process voice message
        chatbot_response = chatbot.chat(sid, text)
        processed_result = await process_text_message(chatbot_response, sid)

        bot_text = processed_result.get("text", chatbot_response)
        bot_audio = processed_result.get("audio") or await generate_voice_response(bot_text, sid)

        logger.info("sent response")
        await sio.emit("bot_reply", {
            "bot_text": bot_text,
            "bot_audio": bot_audio
        }, to=sid)

    except Exception as e:
        logger.error(f"Error in handle_end_voice: {e}")
        await sio.emit("error", {"message": "Failed to process audio"}, to=sid)

@sio.on("ping")
async def handle_ping(sid, data):
    """Health check endpoint"""
    await sio.emit("pong", {"timestamp": datetime.now().isoformat()}, to=sid)