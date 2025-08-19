import os
import socketio   # ✅ you need this
from django.core.asgi import get_asgi_application
from chatbot_project.socketio_app import register_socketio_handlers

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "chatbot_project.settings")

django_asgi_app = get_asgi_application()

# Socket.IO server
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",  # adjust for production
    logger=False,
    engineio_logger=False,
    max_http_buffer_size=10 * 1024 * 1024,  # allow large audio chunks
)

# Register event handlers
register_socketio_handlers(sio)

# Mount Socket.IO at /socket.io, fall through to Django for everything else
application = socketio.ASGIApp(sio, other_asgi_app=django_asgi_app)
