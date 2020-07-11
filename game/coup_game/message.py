import enum
from rest_framework import serializers
from game.coup_game.move import VALID_MOVES
from game.coup_game.turn.state import TurnState
from django.utils.html import escape

class MessageHeader(enum.Enum):
    """Internal and external message types are defined here"""
    CHAT_MESSAGE = 'chat-message'
    GAME_MOVE = 'game-move'

class Message(object):
    def __init__(self, header):
        assert isinstance(header, MessageHeader), "Bad value for header"
        self.header = header

class ChatMessage(Message):
    def __init__(self, player, message):
        super(ChatMessage, self).__init__(MessageHeader.CHAT_MESSAGE)
        self.player = player 
        self.message = message

class GameMove(Message):
    def __init__(self, player, move):
        super(GameMove, self).__init__(MessageHeader.GAME_MOVE)
        self.player = player
        self.move = move

class ChatSerializer(serializers.Serializer):
    player = serializers.CharField(max_length=50)
    message = serializers.CharField(max_length=200)

    def validate_message(self, value):
        return escape(value)

    def create(self):
        if self.validated_data is not None:
            return ChatMessage(**self.validated_data)
        else:
            raise Exception("Must call is_valid() first")

class GameMoveSerializer(serializers.Serializer):
    player = serializers.CharField(max_length=50)
    move = serializers.CharField(max_length=50)

    def validate_move(self, value):
        for valid_move_type in VALID_MOVES:
            try:
                return valid_move_type(value)
            except ValueError:
                pass
        raise serializers.ValidationError(f"Invalid move {value}")

    def create(self):
        if self.validated_data is not None:
            return GameMove(**self.validated_data)
        else:
            raise Exception("Must call is_valid() first")