from rest_framework import serializers
from django.utils.html import escape
import enum
import json

class EventType(enum.Enum):
    CHAT = 'chat'
    GAME_MOVE = 'game.move'
    GAME_CONTROL = 'game.control'

class ChatSerializer(serializers.Serializer):
    type = serializers.CharField(max_length=50)
    player = serializers.CharField(max_length=50)
    message = serializers.CharField(max_length=200)

class GameMoveSerializer(serializers.Serializer):
    type = serializers.CharField(max_length=50)
    player = serializers.CharField(max_length=50)
    move = serializers.CharField(max_length=50)
    target = serializers.CharField(max_length=50, allow_null=True)

class GameControlSerializer(serializers.Serializer):
    type = serializers.CharField(max_length=50)
    player = serializers.CharField(max_length=50)
    control = serializers.CharField(max_length=50)
    value = serializers.IntegerField(max_value=100, min_value=0, allow_null=True)

event_type_to_serializer = {
    EventType.CHAT: ChatSerializer,
    EventType.GAME_MOVE: GameMoveSerializer,
    EventType.GAME_CONTROL: GameControlSerializer
}

def create_serializer(data):
    event_type_str = data.get('type')
    if event_type_str is None:
        raise KeyError('create_serialier: Data missing type field')
    event_type = EventType(event_type_str)
    serializer = event_type_to_serializer[event_type]
    return serializer(data=data)

def text_data_to_data(text_data):
    return json.loads(text_data)

def data_to_text_data(data):
    return json.dumps(data)