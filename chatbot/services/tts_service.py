import base64
import io
import time
from gtts import gTTS
import boto3
from pydub import AudioSegment
import emoji

def clean_text(text: str) -> str:
    """
    Remove emojis and asterisks from the text.
    """
    text = emoji.replace_emoji(text, replace='')  # remove emojis
    text = text.replace('*', '')  # remove asterisks
    return text

async def generate_voice_response(text: str) -> str:
    """
    gTTS -> MP3 (memory) -> WAV (PCM16 mono 16kHz) -> base64
    Emoji characters and asterisks are removed before TTS.
    Prints the time taken for conversion.
    """
    start_time = time.time()  # start timer

    cleaned_text = clean_text(text)
    
    mp3_fp = io.BytesIO()
    tts = gTTS(text=cleaned_text, lang="en")
    tts.write_to_fp(mp3_fp)
    mp3_fp.seek(0)

    audio = AudioSegment.from_file(mp3_fp, format="mp3")
    audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)

    wav_fp = io.BytesIO()
    audio.export(wav_fp, format="wav")
    wav_fp.seek(0)

    end_time = time.time()  # end timer
    print(f"[TTS] Time taken: {end_time - start_time:.3f} seconds")

    return base64.b64encode(wav_fp.read()).decode("utf-8")


# ------------------ Amazon Polly Setup ------------------
AWS_ACCESS_KEY = "AKIAZI2LCCJBIABTVG4K"
AWS_SECRET_KEY = "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"
AWS_REGION = "us-west-2"  # change as needed

polly_client = boto3.Session(
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=AWS_REGION
).client('polly')


async def generate_voice_response_by_poly(text: str, voice: str = "Kajal", engine: str = "neural") -> str:
    """
    Generate voice using Amazon Polly -> PCM16 mono 16kHz WAV -> base64
    Removes emojis and asterisks before sending text to Polly.
    Prints the time taken for conversion.
    """
    start_time = time.time()

    cleaned_text = clean_text(text)

    # Call Polly
    response = polly_client.synthesize_speech(
        Text=cleaned_text,
        OutputFormat='mp3',  # get mp3 first
        VoiceId=voice,
        Engine=engine
    )

    mp3_fp = io.BytesIO(response['AudioStream'].read())
    mp3_fp.seek(0)

    # Convert to WAV 16kHz mono
    audio = AudioSegment.from_file(mp3_fp, format="mp3")
    audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)

    wav_fp = io.BytesIO()
    audio.export(wav_fp, format="wav")
    wav_fp.seek(0)

    end_time = time.time()
    print(f"[Polly TTS] Time taken: {end_time - start_time:.3f} seconds")

    return base64.b64encode(wav_fp.read()).decode("utf-8")
