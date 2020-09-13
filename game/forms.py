from django.forms import ModelForm
from game.models import Room

class RoomForm(ModelForm):
    class Meta:
        model = Room
        fields = ['name', 'password']