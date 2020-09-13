from rest_framework import serializers
from game.models import Room
import enum
import json

class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = ['id', 'name', 'game_started', 'num_players', 'password']