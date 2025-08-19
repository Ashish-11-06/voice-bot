import asyncio
import base64
import io
import json
import wave
import atexit
import numpy as np
from typing import Set
from fractions import Fraction

from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render

from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
from aiortc.contrib.media import MediaBlackhole
from av import AudioFrame  # ✅ use PyAV's AudioFrame

from chatbot.services.tts_service import generate_voice_response  # returns base64 WAV

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
        self._timestamp = 0  # track samples sent

    async def recv(self) -> AudioFrame:
        try:
            pcm_bytes = await asyncio.wait_for(self._queue.get(), timeout=0.2)
        except asyncio.TimeoutError:
            # 20 ms of silence
            num_samples = int(0.02 * self._sample_rate)
            pcm_bytes = b"\x00\x00" * num_samples * self._channels

        pcm = np.frombuffer(pcm_bytes, dtype=np.int16)

        if self._channels == 1:
            pcm = pcm.reshape(1, -1)
        else:
            pcm = pcm.reshape(-1, self._channels).T

        frame = AudioFrame.from_ndarray(pcm, layout="mono" if self._channels == 1 else "stereo")
        frame.sample_rate = self._sample_rate

        # ✅ set pts and time_base so Opus encoder knows timing
        frame.pts = self._timestamp
        frame.time_base = Fraction(1, self._sample_rate)
        self._timestamp += frame.samples  # increment by number of samples

        return frame

    def feed_wav_bytes(self, wav_bytes: bytes):
        # Decode WAV -> enqueue small PCM chunks
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            self._channels = wf.getnchannels()
            self._sample_rate = wf.getframerate()
            width = wf.getsampwidth()
            assert width == 2, "Expect 16-bit PCM WAV from TTS"

            chunk_frames = int(0.02 * self._sample_rate)  # 20 ms
            while True:
                frames = wf.readframes(chunk_frames)
                if not frames:
                    break
                self._queue.put_nowait(frames)


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

    @pc.on("track")
    def on_track(track):
        if track.kind == "audio":
            print("🔊 Received mic track")
            sink.addTrack(track)

    @pc.on("datachannel")
    def on_datachannel(channel):
        print("📡 DataChannel opened:", channel.label)

        @channel.on("message")
        async def on_message(message):
            if isinstance(message, str):
                try:
                    obj = json.loads(message)
                    user_text = obj.get("text") if isinstance(obj, dict) else message
                except Exception:
                    user_text = message
            else:
                return

            if not user_text:
                return

            reply_text = f"Hey, you just said {user_text}"
            b64_wav = await generate_voice_response(reply_text)  # WAV (PCM16, mono, 16k)
            wav_bytes = base64.b64decode(b64_wav)

            bot_track.feed_wav_bytes(wav_bytes)
            channel.send(json.dumps({"bot_text": reply_text}))

    @pc.on("connectionstatechange")
    async def on_state_change():
        print("PC state:", pc.connectionState)
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
