from channels.routing import ProtocolTypeRouter, ChannelNameRouter
from channels.auth import AuthMiddlewareStack
from channels.routing import URLRouter
import game.routing
from game.consumers import  GameEngineConsumer

application = ProtocolTypeRouter({
    # (http->django views is added by default)
    'channel':ChannelNameRouter({
        'game-engine':GameEngineConsumer
    }),
    'websocket': AuthMiddlewareStack(
         URLRouter(
             game.routing.websocket_urlpatterns
         )
    )
})