import logging
import json
from channels.layers import get_channel_layer
from channels.consumer import AsyncConsumer
from channels.generic.websocket import AsyncWebsocketConsumer, JsonWebsocketConsumer
from game.coup_game import CoupGame

names = ['Labrador Dog', 'Guinea Pig', 'Gold Fish', 'Chestnut Mushroom', 'Cordless Brush', 'Green Car']
def get_unique_name():
    import random
    return names.pop()

class PlayerConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.player_name = get_unique_name()

        # Join room group
        await self.channel_layer.group_add(
            self.room_name,
            self.channel_name
        )

        # Join game by sending join_game message to the game engine
        await self.channel_layer.send(
            'game-engine', {
                'type': 'join_game',
                'sender': self.player_name,
                'room_group_name': self.room_name,
                'message': '',
            }
        )
        await self.accept()

        # Disable all player move buttons except for start-game
        await self.send(text_data=json.dumps({
            'header': 'player-valid-moves',
            'message': ['start-game']
        }))

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_name,
            self.channel_name
        )

    # Receive message from WebSocket
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        header = text_data_json.get('header')
        message = text_data_json.get('message')
        logging.info(f'Received message from client {text_data_json}')

        if header == 'chat-message':
            await self.broadcast_message_to_room(message)
        elif header in ('game-actions', 'game-counteractions', 'game-challenge'):
            pass
        elif header == 'start-game':
            await self.send_message_to_game_engine(handler='start_game', message=None)
        else:
            logging.error(f"Received bad message type {header}: {message} from client")

    async def room_chat_message(self, event):
        """Receive room chat message from channel layer"""
        message = f"{event.get('sender')}: {event.get('message')}"
        # Send message to WebSocket
        await self.send_message_to_client(header='chat-message', message=message)
    
    async def game_engine_message(self, event):
        """Receive message from game engine, then propagate message to the client."""
        logging.info(f'Received message from game-engine {event}')
        await self.send_message_to_client(header=event.get('header'), message=event.get('message'))
    
    async def game_message(self, event):
        logging.info(f'Received message from game {event}')
        await self.send_message_to_client(header=event.get('header'), message=event.get('message'))

    async def game_state_update(self, event):
        """Update interface of the client (valid buttons etc.)
        {
            player0: {
                'player-valid-moves': [
                    'challenge',
                ]
            }
            player1: {
                'player-valid-moves': [
                ]
            }
        }
        """
        game_state_message = event.get('message')
        if self.player_name not in game_state_message:
            logging.error(f"Missing player {self.player_name}in game state update {game_state_message}")
            return
        player_game_state_message = game_state_message.get(self.player_name)
        logging.debug(f"Sending game state {player_game_state_message}")
        await self.send_message_to_client(
            header=player_game_state_message.get('header'), 
            message=player_game_state_message.get('message')
        )
    
    async def send_message_to_client(self, header, message):
        logging.info(f'Send message to client {header}:{message}')
        await self.send(
            text_data=json.dumps(
                {
                    'header': header,
                    'message': message
                }
            )
        )
    
    async def send_message_to_game_engine(self, handler, message):
        await self.channel_layer.send(
            'game-engine', {
                'type': handler,
                'sender': self.player_name,
                'room_group_name': self.room_name,
                'message': message
            }
        )
    async def broadcast_message_to_room(self, message):
        await self.channel_layer.group_send(
            self.room_name, {
                'type': 'room_chat_message',
                'sender': self.player_name,
                'message': message
            }
        )

class GameEngineConsumer(AsyncConsumer):
    """Game engine manages currently ongoing games, redirect incoming messages to current games by room name.
    The indiividual game instance will broadcast update messages."""
    def __init__(self, *args, **kwargs):
        super(GameEngineConsumer,self).__init__(*args, **kwargs)
        self.name = 'game-engine'
        self.channel_layer = get_channel_layer()
        self.games = dict()
    
    async def start_game(self, event):
        logging.info(f"Received message {event}")
        room_name = event.get('room_group_name')
        room_game = self.games[room_name]
        await room_game.start_game()

    async def join_game(self, event):
        logging.info(f"Received message {event}")
        room_name = event.get('room_group_name')
        new_player = event.get('sender')

        if room_name in self.games:
            self.games[room_name].add_player(new_player)
        else:
            self.games[room_name] = CoupGame(room_name)
            self.games[room_name].add_player(new_player)

        await self.games[room_name].ping()
        await self.broadcast_message_to_room(room_name, header='player-list', message=self.games[room_name].get_player_names())
        await self.broadcast_message_to_room(room_name, header='chat-message', message=f"Master: {new_player} joined the room")
    
    async def broadcast_message_to_room(self, room_name, header, message):
        logging.info(f'game-engine broadcasting header:{header}, message:{message}')
        await self.channel_layer.group_send(
            room_name, {
                'type': 'game_engine_message',
                'header': header,
                'message': message
            }
        )