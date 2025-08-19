# socketio_app.py
import base64
from typing import Dict

import socketio
from chatbot.services.stt_service import STTSession
from chatbot.services.tts_service import generate_voice_response

# Keep per-connection STT sessions
_sessions: Dict[str, STTSession] = {}


def register_socketio_handlers(sio: socketio.AsyncServer):

    @sio.event
    async def connect(sid, environ):
        # Create a new STT session per client
        _sessions[sid] = STTSession()
        await sio.emit("ready", {"ok": True}, to=sid)

    @sio.event
    async def disconnect(sid):
        sess = _sessions.pop(sid, None)
        if sess:
            await sess.aclose()

    # ✅ Handle plain text messages (from frontend SpeechRecognition)
    @sio.on("user_message")
    async def handle_user_message(sid, data):
        """
        Handles text input directly from client.
        Expects: {"text": "hello bot"}
        """
        text = None
        if isinstance(data, dict):
            text = data.get("text")
        elif isinstance(data, str):
            text = data

        if not text:
            return

        # Echo as bot reply
        bot_text = f"Hey hii, you just said {text}"
        audio_b64 = await generate_voice_response(bot_text)

        await sio.emit(
            "bot_response",
            {"text": bot_text, "audio": audio_b64},
            to=sid,
        )

    # ✅ Optional: keep audio streaming logic if you later switch to mic streaming
    @sio.on("start_stream")
    async def start_stream(sid, data):
        sess = _sessions.get(sid)
        if sess:
            await sess.reset()
        await sio.emit("stt_status", {"status": "listening"}, to=sid)

    @sio.on("mic_chunk")
    async def mic_chunk(sid, blob_bytes):
        """
        Receives raw binary chunk (webm/opus) from client.
        Decodes → feeds to recognizer → emits partial/final.
        """
        sess = _sessions.get(sid)
        if not sess:
            return

        async for kind, text in sess.feed_webm_opus(blob_bytes):
            if kind == "partial" and text:
                await sio.emit("stt_partial", {"text": text}, to=sid)
            elif kind == "final" and text:
                await sio.emit("stt_result", {"text": text}, to=sid)

                # Bot reply
                bot_text = f"Hey hii, you just said {text}"
                audio_b64 = await generate_voice_response(bot_text)
                await sio.emit(
                    "bot_response",
                    {"text": bot_text, "audio": audio_b64},
                    to=sid,
                )

    @sio.on("stop_stream")
    async def stop_stream(sid):
        sess = _sessions.get(sid)
        if not sess:
            return

        final_text = await sess.flush()
        if final_text:
            await sio.emit("stt_result", {"text": final_text}, to=sid)

            bot_text = f"Hey hii, you just said {final_text}"
            audio_b64 = await generate_voice_response(bot_text)
            await sio.emit(
                "bot_response",
                {"text": bot_text, "audio": audio_b64},
                to=sid,
            )
