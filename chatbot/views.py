import asyncio
import base64
import io
import json
import wave
from typing import Set

from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render

from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
from aiortc.mediastreams import AudioFrame
from aiortc.contrib.media import MediaBlackhole

from chatbot.services.tts_service import generate_voice_response  # <- your TTS (returns base64 WAV)

# Keep references so they don’t get GC’ed
pcs: Set[RTCPeerConnection] = set()


def index(request):
    return render(request, "index.html")


class BotAudioTrack(MediaStreamTrack):
    """
    A server-side audio track which we can 'feed' with WAV bytes
    and it will stream them to the client as PCM frames.
    """
    kind = "audio"

    def __init__(self):
        super().__init__()
        self._queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._closed = False
        self._sample_rate = 16000  # default; will be corrected per clip
        self._channels = 1

    async def recv(self) -> AudioFrame:
        """
        Pulls PCM S16LE bytes from queue, converts to an AudioFrame.
        If queue is empty, emits silence to keep the track alive.
        """
        # wait a short time for data; otherwise send silence
        try:
            chunk = await asyncio.wait_for(self._queue.get(), timeout=0.2)
        except asyncio.TimeoutError:
            # 20ms silence at current sample rate
            num_samples = int(0.02 * self._sample_rate)
            pcm = b"\x00\x00" * num_samples * self._channels
            frame = AudioFrame.from_ndarray(
                pcm, layout="mono" if self._channels == 1 else "stereo", format="s16"
            )
            frame.sample_rate = self._sample_rate
            return frame

        # chunk is raw PCM s16le
        frame = AudioFrame.from_ndarray(
            chunk, layout="mono" if self._channels == 1 else "stereo", format="s16"
        )
        frame.sample_rate = self._sample_rate
        return frame

    def feed_wav_bytes(self, wav_bytes: bytes):
        """
        Decode WAV bytes -> push PCM chunks into the queue.
        """
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            self._channels = wf.getnchannels()
            self._sample_rate = wf.getframerate()
            width = wf.getsampwidth()
            assert width == 2, "Expect 16-bit PCM WAV from TTS"

            # push small chunks (~20ms) for smoother playback
            chunk_frames = int(0.02 * self._sample_rate)  # 20ms
            while True:
                frames = wf.readframes(chunk_frames)
                if not frames:
                    break
                # frames is already s16le PCM
                # enqueue raw bytes
                self._queue.put_nowait(frames)

    async def aclose(self):
        self._closed = True
        await super().stop()


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

    # Create server -> client audio track (TTS will feed this)
    bot_track = BotAudioTrack()
    pc.addTrack(bot_track)

    # Optional: If you want to discard inbound audio for now
    sink = MediaBlackhole()

    @pc.on("track")
    def on_track(track):
        # If later you stream mic to server, you can process it here for STT
        if track.kind == "audio":
            print("🔊 Received mic track")
            sink.addTrack(track)

    @pc.on("datachannel")
    def on_datachannel(channel):
        print("📡 DataChannel opened:", channel.label)

        @channel.on("message")
        async def on_message(message):
            """
            We expect either plain text (string) or JSON like {"text": "..."}.
            We'll TTS: "Hey, you just said <text>"
            """
            if isinstance(message, str):
                try:
                    obj = json.loads(message)
                    user_text = obj.get("text") if isinstance(obj, dict) else message
                except Exception:
                    user_text = message
            else:
                # ignore binary for now
                return

            if not user_text:
                return

            reply_text = f"Hey, you just said {user_text}"
            # Your TTS returns base64 WAV
            b64_wav = await generate_voice_response(reply_text)
            wav_bytes = base64.b64decode(b64_wav)

            # feed to our outgoing track
            bot_track.feed_wav_bytes(wav_bytes)

            # (Optional) also inform the client via channel text
            channel.send(json.dumps({"bot_text": reply_text}))

    @pc.on("connectionstatechange")
    async def on_state_change():
        print("PC state:", pc.connectionState)
        if pc.connectionState in ("failed", "closed", "disconnected"):
            await cleanup_pc(pc)

    # Apply offer/answer
    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return JsonResponse(
        {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
    )


async def cleanup_pc(pc: RTCPeerConnection):
    if pc in pcs:
        pcs.remove(pc)
    await pc.close()

@atexit.register
def close_pcs():
    coros = [pc.close() for pc in list(pcs)]
    if coros:
        asyncio.get_event_loop().run_until_complete(asyncio.gather(*coros))