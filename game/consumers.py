import logging
import json
from channels.layers import get_channel_layer
from channels.consumer import AsyncConsumer
from channels.generic.websocket import AsyncWebsocketConsumer
from game.coup_game import CoupGame

class PlayerConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.player_name = self.scope['user'].username

        # Join room group
        await self.channel_layer.group_add(
            self.room_name,
            self.channel_name
        )

        # Join game by sending join_room message to the game manager
        await self.channel_layer.send(
            'room-manager', {
                'type': 'join_room',
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
        logging.debug(f'Received message from client:\n{json.dumps(text_data_json, indent=4)}')

        if header == 'chat-message':
            await self.broadcast_message_to_room(message)
        elif header == 'game-move':
            await self.send_message_to_room_manager(handler='game_move', message=message)
        elif header == 'start-game':
            await self.send_message_to_room_manager(handler='start_game', message=None)
        else:
            logging.error(f"Received bad message {header}: {message} from client")

    async def room_chat_message(self, event):
        """Receive room chat message from channel layer"""
        message = f"{event.get('sender')}: {event.get('message')}"
        # Send message to WebSocket
        await self.send_message_to_client(header='chat-message', message=message)
    
    async def room_manager_message(self, event):
        """Receive message from game engine, then propagate message to the client."""
        logging.debug(f'Received message from room-manager:\n{json.dumps(event, indent=4)}')
        await self.send_message_to_client(header=event.get('header'), message=event.get('message'))
    
    async def game_message(self, event):
        logging.debug(f'Received message from game:\n {json.dumps(event, indent=4)}')
        await self.send_message_to_client(header=event.get('header'), message=event.get('message'))

    async def game_state_update(self, event):
        """Update interface of the client (valid buttons etc.)"""
        game_state_message = event.get('message')
        if self.player_name not in game_state_message:
            #logging.error(f"Missing player {self.player_name} in game state update {event}")
            return
        player_game_state_message = game_state_message.get(self.player_name)
        logging.debug(f"Sending game state {player_game_state_message}")
        await self.send_message_to_client(
            header=player_game_state_message.get('header'), 
            message=player_game_state_message.get('message')
        )
    
    async def send_message_to_client(self, header, message):
        logging.debug(f'Send message to client {self.player_name}:\n{header}:{json.dumps(message, indent=4)}')
        await self.send(
            text_data=json.dumps(
                {
                    'header': header,
                    'message': message
                }
            )
        )
    
    async def send_message_to_room_manager(self, handler, message):
        await self.channel_layer.send(
            'room-manager', {
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

class RoomManagerConsumer(AsyncConsumer):
    """Room manager manages currently ongoing games, redirect incoming messages to current games by room name.
    The indiividual game instance will broadcast update messages."""
    def __init__(self, *args, **kwargs):
        super(RoomManagerConsumer,self).__init__(*args, **kwargs)
        self.name = 'room-manager'
        self.channel_layer = get_channel_layer()
        self.games = dict()

    async def game_move(self, event):
        logging.debug(f"Received message:\n{json.dumps(event, indent=4)}")
        message = event.get('message')
        room_name = event.get('room_group_name')
        room_game = self.games[room_name]
        player_name = event.get('sender')
        move_type = message.get('type')
        move = message.get('move')
        target = message.get('target')

        if move_type == 'select-influence':
            await self.broadcast_message_to_room(room_name, header='chat-message', message=f"Master: {player_name} selected {move}")
        elif target:
            await self.broadcast_message_to_room(room_name, header='chat-message', message=f"Master: {player_name} used {move} on {target}")
        else:
            await self.broadcast_message_to_room(room_name, header='chat-message', message=f"Master: {player_name} used {move}")

        await room_game.update_game_state_with_move(player_name=player_name, move_type=message.get('type'), move=move, target=target)
        await room_game.broadcast_game_state()
        await room_game.broadcast_player_state()
        import pprint
        logging.info(pprint.pformat(room_game.game_state, indent=4))
    
    async def start_game(self, event):
        logging.debug(f"Received message:\n{json.dumps(event, indent=4)}")
        room_name = event.get('room_group_name')
        room_game = self.games[room_name]
        await room_game.start_game()
        await room_game.broadcast_game_state()
        await room_game.broadcast_player_state()

    async def join_room(self, event):
        logging.debug(f"Received message\n{json.dumps(event, indent=4)}")
        room_name = event.get('room_group_name')
        new_player = event.get('sender')

        if room_name in self.games:
            self.games[room_name].add_player(new_player)
        else:
            self.games[room_name] = CoupGame(room_name)
            self.games[room_name].add_player(new_player)

        await self.broadcast_message_to_room(room_name, header='player-list', message=self.games[room_name].get_player_names())
        await self.broadcast_message_to_room(room_name, header='chat-message', message=f"Master: {new_player} joined the room")
    
    async def broadcast_message_to_room(self, room_name, header, message):
        logging.debug(f'room-manager broadcasting {header}\n{json.dumps(message, indent=4)}')
        await self.channel_layer.group_send(
            room_name, {
                'type': 'room_manager_message',
                'header': header,
                'message': message
            }
        )