from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/voice-chat/$', consumers.VoiceChatConsumer.as_asgi()),
]