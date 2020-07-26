import logging
import json
from channels.layers import get_channel_layer
from channels.consumer import AsyncConsumer
from channels.generic.websocket import AsyncWebsocketConsumer
from game.coup_game.coup_game import CoupGame, CoupGameFrontend
from game.coup_game.move import str_to_move
import game.serializers as serializers

class PlayerConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.player_name = self.scope['user'].username
        self.channel_layer_sender = ChannelLayerMessageSender(self.channel_layer)

        await self.channel_layer.group_add(self.room_name, self.channel_name)
        await self.channel_layer_sender.send_to_consumer('room-manager', 
            {'type': 'join.game', 'player':self.player_name, 'room': self.room_name}
        )
        await self.accept()
        logging.info(f'Joined {self.player_name}')

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_name, self.channel_name)

    async def receive(self, text_data):
        data = serializers.text_data_to_data(text_data)
        logging.debug(f'Received data {data}')

        try:
            serializer = serializers.create_serializer(data)
        except Exception as ex:
            resp = {'errors': str(ex)}
            await self.send(text_data=json.dumps(resp))
            logging.error(f'Error: Serializer raised an exception for data {data}. {ex}')
        else:
            if serializer.is_valid():
                await self._process_or_propagate_message(serializer.validated_data)
            else:
                resp = {'errors': serializer.errors}
                await self.send(text_data=json.dumps(resp))
                logging.error(f'Error: Serializered data is not valid. {serializer.errors}')
    
    async def _process_or_propagate_message(self, validated_data):
        event_type = serializers.EventType(validated_data['type'])
        if event_type is serializers.EventType.CHAT:
            await self.channel_layer_sender.broadcast_to_group(self.room_name, validated_data)
        elif event_type in (serializers.EventType.GAME_MOVE, serializers.EventType.GAME_CONTROL):
            validated_data['room'] = self.room_name
            await self.channel_layer_sender.send_to_consumer('room-manager', validated_data)
        else:
            logging.error(f'Received unexpected event type {event_type} data {validated_data}')
    
    async def chat(self, event):
        await self.send(text_data=serializers.data_to_text_data(event))
    
    async def frontend_update(self, event):
        await self.send(text_data=serializers.data_to_text_data(event))

    async def individual_frontend_update(self, event):
        """Pick up the event addressed to this player and pass it to client"""
        if self.player_name not in event:
            logging.error(f'No update for player {self.player_name} in individual update event {event}')
            resp = {'errors': 'Internal server error. No update for player'}
            await self.send(text_data=json.dumps(resp))
            import pdb; pdb.set_trace()
            return
        player_event = event[self.player_name]
        player_event['type'] = 'frontend.update'
        await self.send(text_data=serializers.data_to_text_data(player_event))
    
import enum
class Control(enum.Enum):
    START_GAME = 'start.game'
    JOIN_GAME = 'join.game'
    PAUSE_GAME = 'pause.game'
    GAME_UPDATE = 'game.update'

    @classmethod
    def from_str(cls, string_key):
        return cls[string_key.upper()]

class RoomManagerConsumer(AsyncConsumer):
    """Room manager manages currently ongoing games, redirect incoming messages to current games by room name.
    The indiividual game instance will broadcast update messages."""
    def __init__(self, *args, **kwargs):
        super(RoomManagerConsumer,self).__init__(*args, **kwargs)
        self.games = dict()     # Current ongoing games by room id
        self.channel_layer_sender= ChannelLayerMessageSender(get_channel_layer())
        self.coup_frontend = CoupGameFrontend()
        logging.info('Room manager initialized')
    
    async def game_move(self, event):
        room = event.get('room')
        game = self.games[room]

        # Convert string to objects
        move = str_to_move(event.get('move'))
        player = game.get_player_by_name(event.get('player'))
        target = None
        if event.get('target'):
            target = game.get_player_by_name(event.get('target'))
        game.player_make_move(player=player, move=move, target=target)
        await self._send_frontend_to_players(room, game)
    
    async def game_control(self, event):
        # Process event
        room = event.get('room')
        game = self.games[room]
        if event.get('control') == 'start-game':
            game.start()
        elif event.get('control') == 'change-seat':
            player = game.get_player_by_name(event.get('player'))
            seat = event.get('value')
            game.player_change_seat(player, seat)
        await self._send_frontend_to_players(room, game)
    
    async def join_game(self, event):
        player = event.get('player')
        room = event.get('room')
        if not room in self.games:
            self.games[room] = CoupGame(room)
        game = self.games[room]

        player_obj = game.add_player(player)

        # Send chat message to clients to inform new player join
        if player_obj:
            await self._send_chat_to_players(room, f'{player} has joined the room')
        else:
            await self._send_chat_to_players(room, f'{player} has re-joined the room')
        await self._send_frontend_to_players(room, game)

    async def _send_chat_to_players(self, room, message):
        await self.channel_layer_sender.broadcast_to_group(room, {
            'type': 'chat',
            'player': 'Game Master',
            'message': message
        })

    async def _send_frontend_to_players(self, room, game):
        await self.channel_layer_sender.broadcast_to_group(room, {
            'type': 'frontend.update',
            'game_view': self.coup_frontend.game_view(game)
        })

        individual_update = {'type': 'individual.frontend.update'}
        for player in game.players:
            individual_update[player.name] = {'interface': self.coup_frontend.player_interface(game, player)}
        await self.channel_layer_sender.broadcast_to_group(room, individual_update)
            
class ChannelLayerMessageSender(object):
    def __init__(self, channel_layer):
        self._channel_layer = channel_layer
    
    async def broadcast_to_group(self, group_name, data):
        logging.info(f'Broadcasting to {group_name} : {data}')
        await self._channel_layer.group_send(group_name, data)

    async def send_to_consumer(self, consumer_name, data):
        logging.info(f'Sending to consumer {consumer_name} : {data}')
        await self._channel_layer.send(consumer_name, data)