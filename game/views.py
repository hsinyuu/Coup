from django.shortcuts import render
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login


def lobby_view(request):
	return render(request, 'game/pages/lobby.html')

@login_required
def room_view_old(request, room_name):
	return render(request, 'game/pages/room_old.html', context={'room_name':room_name})

@login_required
def room_view(request, room_name):
	return render(request, 'game/pages/room.html', context={'room_name':room_name})

def test_view(request):
	#Must specify type. Type is the consumers function
	data = {
	'type': 'game.move',
	'room-id':None,
	'move':None,
	'target':None
	}
	channel_layer = get_channel_layer()
	async_to_sync(channel_layer.send)('room-manager', data)

	return render(request, 'game/index.html')

def login_view(request):
    username = request.POST['username']
    password = request.POST['password']
    user = authenticate(request, username=username, password=password)
    if user is not None:
        login(request, user)
        return HttpResponseRedirect('/lobby/')