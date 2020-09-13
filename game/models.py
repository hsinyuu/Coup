from django.db import models

class Room(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=100, unique=True)
    game_started = models.BooleanField(default=False)
    num_players = models.IntegerField()
    password = models.CharField(max_length=256)