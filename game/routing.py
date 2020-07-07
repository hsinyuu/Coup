from . import consumers
from django.urls import path, re_path
 
websocket_urlpatterns = [ 
    re_path(r'ws/message/(?P<room_name>\w+)/$', consumers.PlayerConsumer),
]
