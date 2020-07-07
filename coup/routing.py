from channels.routing import ProtocolTypeRouter, ChannelNameRouter
from channels.auth import AuthMiddlewareStack
from channels.routing import URLRouter
import game.routing
from game.consumers import  RoomManagerConsumer
from channels.auth import AuthMiddlewareStack


application = ProtocolTypeRouter({
    # (http->django views is added by default)
    'channel':ChannelNameRouter({
        'room-manager':RoomManagerConsumer
    }),
    'websocket': AuthMiddlewareStack(
         URLRouter(
             game.routing.websocket_urlpatterns
         )
    )
})