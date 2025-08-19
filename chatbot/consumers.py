import json
from channels.generic.websocket import AsyncWebsocketConsumer
from .services.tts_service import generate_voice_response

class VoiceChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        await self.send_voice_response()

    async def receive(self, text_data):
        # For now just respond with the same message
        await self.send_voice_response()

    async def send_voice_response(self):
        response = {
            "text": "Hello, I am Ruby. I am not fully developed yet, please wait!",
            "audio": await generate_voice_response()
        }
        await self.send(text_data=json.dumps(response))