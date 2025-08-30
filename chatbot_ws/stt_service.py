import whisper
import tempfile
import wave

model = whisper.load_model("base")  # small/base/medium/large

def transcribe_pcm16_audio(audio_data: bytes, sample_rate: int = 16000) -> str:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmpfile:
        with wave.open(tmpfile, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio_data)
        tmp_path = tmpfile.name

    result = model.transcribe(tmp_path)
    os.unlink(tmp_path)
    return result.get("text", "[Unrecognized Speech]")
