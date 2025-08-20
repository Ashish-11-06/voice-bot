import asyncio
import base64
import io
import json
import wave
import atexit
from fractions import Fraction
from typing import Set, Optional

from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render

import numpy as np
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
from aiortc.contrib.media import MediaBlackhole
from av import AudioFrame, AudioResampler

from chatbot.services.tts_service import generate_voice_response

# --- Vosk STT ---
import os
from vosk import Model, KaldiRecognizer

# VOSK_MODEL_PATH = os.environ.get("VOSK_MODEL_PATH", "./vosk-model-small-en-us-0.15")
VOSK_MODEL_PATH = "/home/ashish/PP/bot/voice_chatbot/chatbot_project/vosk-model-small-en-us-0.15/vosk-model-small-en-us-0.15"
VOSK_SAMPLE_RATE = 16000

_vosk_model: Optional[Model] = None
def get_vosk_model() -> Model:
    global _vosk_model
    if _vosk_model is None:
        if not os.path.isdir(VOSK_MODEL_PATH):
            raise RuntimeError(
                f"Vosk model not found at '{VOSK_MODEL_PATH}'"
            )
        _vosk_model = Model(VOSK_MODEL_PATH)
    return _vosk_model


pcs: Set[RTCPeerConnection] = set()


def index(request):
    return render(request, "index.html")


class BotAudioTrack(MediaStreamTrack):
    kind = "audio"

    def __init__(self):
        super().__init__()
        self._queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._sample_rate = 16000
        self._channels = 1
        self._timestamp = 0

    async def recv(self) -> AudioFrame:
        try:
            pcm_bytes = await asyncio.wait_for(self._queue.get(), timeout=0.2)
        except asyncio.TimeoutError:
            num_samples = int(0.02 * self._sample_rate)
            pcm_bytes = b"\x00\x00" * num_samples * self._channels

        pcm = np.frombuffer(pcm_bytes, dtype=np.int16)
        if self._channels == 1:
            pcm = pcm.reshape(1, -1)
        else:
            pcm = pcm.reshape(-1, self._channels).T

        frame = AudioFrame.from_ndarray(
            pcm, layout="mono" if self._channels == 1 else "stereo"
        )
        frame.sample_rate = self._sample_rate
        frame.pts = self._timestamp
        frame.time_base = Fraction(1, self._sample_rate)
        self._timestamp += frame.samples
        return frame

    def feed_wav_bytes(self, wav_bytes: bytes):
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            self._channels = wf.getnchannels()
            self._sample_rate = wf.getframerate()
            width = wf.getsampwidth()
            assert width == 2, "Expect 16-bit PCM WAV from TTS"

            chunk_frames = int(0.02 * self._sample_rate)
            while True:
                frames = wf.readframes(chunk_frames)
                if not frames:
                    break
                self._queue.put_nowait(frames)


async def stt_stream(track: MediaStreamTrack, bot_track: BotAudioTrack, send_fn):
    """
    Consume incoming mic audio -> Vosk STT -> generate TTS reply -> feed BotAudioTrack
    """
    resampler = AudioResampler(format="s16", layout="mono", rate=VOSK_SAMPLE_RATE)
    recognizer = KaldiRecognizer(get_vosk_model(), VOSK_SAMPLE_RATE)
    recognizer.SetWords(True)

    send_fn({"info": "STT ready (Vosk 16kHz mono)"})

    try:
        while True:
            frame: AudioFrame = await track.recv()
            mono16 = resampler.resample(frame)

            # Handle list vs single frame
            frames = mono16 if isinstance(mono16, list) else [mono16]

            for f in frames:
                pcm = f.to_ndarray()
                if pcm.ndim == 2:
                    pcm = pcm[0]
                pcm_bytes = pcm.astype(np.int16, copy=False).tobytes()

                if recognizer.AcceptWaveform(pcm_bytes):
                    result = json.loads(recognizer.Result())
                    text = (result.get("text") or "").strip()
                    if text:
                        send_fn({"user_text": text})
                        reply_text = f"you just said {text}"
                        send_fn({"bot_text": reply_text})
                        b64_wav = await generate_voice_response(reply_text)
                        bot_track.feed_wav_bytes(base64.b64decode(b64_wav))
    except asyncio.CancelledError:
        pass
    except Exception as e:
        send_fn({"info": f"STT error: {e}"})


@csrf_exempt
async def webrtc_offer(request):
    if request.method != "POST":
        return HttpResponseBadRequest("POST only")

    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return HttpResponseBadRequest("Invalid JSON")

    offer = RTCSessionDescription(sdp=data["sdp"], type=data["type"])
    pc = RTCPeerConnection()
    pcs.add(pc)

    bot_track = BotAudioTrack()
    pc.addTrack(bot_track)
    sink = MediaBlackhole()
    dc_holder = {"channel": None}

    def send_json(obj: dict):
        ch = dc_holder["channel"]
        if ch and ch.readyState == "open":
            ch.send(json.dumps(obj))

    @pc.on("datachannel")
    def on_datachannel(channel):
        dc_holder["channel"] = channel
        channel.send(json.dumps({"info": "DataChannel connected"}))

        @channel.on("message")
        async def on_message(message):
            try:
                obj = json.loads(message) if isinstance(message, str) else {}
                user_text = obj.get("text")
                if user_text:
                    send_json({"user_text": user_text})
                    reply_text = f"you just said {user_text}"
                    send_json({"bot_text": reply_text})
                    b64_wav = await generate_voice_response(reply_text)
                    bot_track.feed_wav_bytes(base64.b64decode(b64_wav))
            except Exception as e:
                send_json({"info": f"DC error: {e}"})

    stt_task: Optional[asyncio.Task] = None

    @pc.on("track")
    def on_track(track):
        nonlocal stt_task
        if track.kind == "audio":
            if stt_task is None or stt_task.done():
                stt_task = asyncio.create_task(stt_stream(track, bot_track, send_json))
        else:
            sink.addTrack(track)

    @pc.on("connectionstatechange")
    async def on_state_change():
        if pc.connectionState in ("failed", "closed", "disconnected"):
            await cleanup_pc(pc)

    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return JsonResponse({"sdp": pc.localDescription.sdp, "type": pc.localDescription.type})


async def cleanup_pc(pc: RTCPeerConnection):
    if pc in pcs:
        pcs.remove(pc)
    await pc.close()


@atexit.register
def close_pcs():
    coros = [pc.close() for pc in list(pcs)]
    if coros:
        asyncio.get_event_loop().run_until_complete(asyncio.gather(*coros))
