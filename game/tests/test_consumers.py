import pytest
import json
from django.test import TestCase, override_settings
from channels.testing import WebsocketCommunicator
from game.consumers import PlayerConsumer, RoomManagerConsumer
from coup.routing import application

## Need to run worker before this test

@override_settings( CHANNEL_LAYERS={ "default": { "BACKEND": "channels.layers.InMemoryChannelLayer", }, })
@pytest.mark.asyncio
async def test_send_chat_message_and_get_response():
    communicator = WebsocketCommunicator(application, 'ws/message/test_room/')
    connected, subprotocol = await communicator.connect()
    assert connected
    event = await communicator.receive_json_from()
    print(event)

    chat_message = {
        'type': 'chat',
        'player': 'bob',
        'message': 'hello'
    }

    await communicator.send_to(text_data=json.dumps(chat_message))
    event = await communicator.receive_json_from()

    # Expect chat message to be broadcasted, including the current player
    for key, val in event.items():
        assert event[key] == chat_message[key]

'''
@override_settings( CHANNEL_LAYERS={ "default": { "BACKEND": "channels.layers.InMemoryChannelLayer", }, })
@pytest.mark.asyncio
async def test_send_start_game_and_get_response():
    communicator = WebsocketCommunicator(application, 'ws/message/test_room/')
    connected, subprotocol = await communicator.connect()
    assert connected
    event = await communicator.receive_json_from()

    game_move_message = {
        'type': 'game.move',
        'player': 'bob',
        'move': 'income',
        'target': None
    }

    await communicator.send_to(text_data=json.dumps(game_move_message))
    event = await communicator.receive_json_from()
    import pdb; pdb.set_trace()

Game Move message when player makes a move
{
    'type': 'game.move',
    'player': 'bob',
    'move': 'income',
    'target': 'john',
}

Game control message for game utilities
{
    'type': 'game.control',
    'player': 'bob',
    'control': 'start-game',
}

Frontend update response from the game master
{
    'type': 'frontend.update',
    'game-view': [
        {
            'player': 'bob',
            'seat': 2,
            'coins': 3,
            'cards': ['flipped', 'duke'],
            'status': 'in-game',
            'turn': false
        },
        {
            'player': 'tom',
            'seat': 3,
            'coins': 0,
            'cards': ['flipped', 'flipped'],
            'status': 'in-game',
            'turn': false
        },
        {
            'player': 'john',
            'seat': 2,
            'coins': 2,
            'cards': ['flipped', 'duke'],
            'status': 'in-game',
            'turn': false
        },
        ...
    ]
    'interface': [
        'start-game',
        'pause-game',
        'challenge',
        'income',
        'steal',
        'exchange',
        'assassinate',
        ...
    ]
}
'''