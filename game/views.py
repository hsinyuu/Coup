from django.shortcuts import render
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

def lobby_view(request):
	return render(request, 'game/pages/lobby.html')

def room_view(request, room_name):
	return render(request, 'game/pages/room.html', context={'room_name':room_name})

def test_view(request):
	#Must specify type. Type is the consumers function
	data = {
	'type':'ping_from_view'
	}
	channel_layer = get_channel_layer()
	async_to_sync(channel_layer.send)('game-engine', data)

	return render(request, 'game/index.html')