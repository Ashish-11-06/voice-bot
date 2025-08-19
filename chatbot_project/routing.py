from channels.routing import ProtocolTypeRouter, URLRouter
import chatbot.routing

application = ProtocolTypeRouter({
    "websocket": URLRouter(
        chatbot.routing.websocket_urlpatterns
    ),
})