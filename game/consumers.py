import logging
import json
from asgiref.sync import async_to_sync
from threading import Timer
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from channels.consumer import AsyncConsumer
from channels.generic.websocket import AsyncWebsocketConsumer
from game.models import Room
from game.coup_game.coup_game import CoupGame, CoupGameFrontend
from game.coup_game.move import str_to_move
from game.coup_game.objects import str_to_inf
from game.coup_game.exceptions import BadPlayerMove, BadGameState, BadTurnState
from django.db import IntegrityError
import game.serializers as serializers

class PlayerConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.player_name = self.scope['user'].username
        self.channel_layer_sender = ChannelLayerMessageSender(self.channel_layer)
        self.move_timeout_timer = None

        await self.channel_layer.group_add(self.room_name, self.channel_name)
        await self.channel_layer_sender.send_to_consumer('room-manager', 
            {'type': 'join.game', 'player':self.player_name, 'room': self.room_name}
        )
        await self.accept()
        logging.info(f'Joined {self.player_name}')

    async def disconnect(self, close_code):
        print('disconnect')
        await self.channel_layer_sender.send_to_consumer('room-manager', 
            {'type': 'disconnect.from.game', 'player':self.player_name, 'room': self.room_name}
        )
        await self.channel_layer.group_discard(self.room_name, self.channel_name)

    async def receive(self, text_data):
        data = serializers.text_data_to_data(text_data)
        logging.info(f'Received data {data}')

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
            return
        player_event = event[self.player_name]
        player_event['type'] = 'frontend.update'
        await self.send(text_data=serializers.data_to_text_data(player_event))

    async def _process_or_propagate_message(self, validated_data):
        event_type = serializers.EventType(validated_data['type'])
        if event_type is serializers.EventType.CHAT:
            await self.channel_layer_sender.broadcast_to_group(self.room_name, validated_data)
        elif event_type in (serializers.EventType.GAME_MOVE, serializers.EventType.GAME_CONTROL):
            validated_data['room'] = self.room_name
            await self.channel_layer_sender.send_to_consumer('room-manager', validated_data)
        else:
            logging.error(f'Received unexpected event type {event_type} data {validated_data}')
    

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
        self.move_timeout = dict()
        self.channel_layer_sender= ChannelLayerMessageSender(get_channel_layer())
        self.coup_frontend = CoupGameFrontend()
        self.db_interface = RoomManagerToDBInterface()
        logging.info('Room manager initialized')
    
    async def game_move(self, event):
        def target_str_to_obj(target):
            if target:
                target_player = game.get_player_by_name(event.get('target'))
                target_card = str_to_inf(event.get('target'))
                if target_player:
                    return target_player
                elif target_card:
                    return target_card
            return None

        room = event.get('room')
        game = self.games[room]

        # Clear internal move timer
        self.clear_move_timer(room)

        # Convert string to objects
        move = str_to_move(event.get('move'))
        player = game.get_player_by_name(event.get('player'))
        target = target_str_to_obj(event.get('target'))
        try:
            game.player_make_move(player=player, move=move, target=target)
        except BadPlayerMove as ex:
            logging.error(ex)
        except BadTurnState as ex:
            logging.error(ex)
        except BadGameState as ex:
            logging.error(ex)
        if target:
            await self._send_chat_to_players(room, f'{player} used {move} on {target}')
        else:
            await self._send_chat_to_players(room, f'{player} used {move}')

        if game.finished:
            winner = game.get_winner()
            logging.info(f"Game finished. Winner: {winner.name}")
            await self._send_chat_to_players(room, f'Game finished. Winner {winner.name} ')
        await self._send_frontend_to_players(room, game)
        self.start_move_timer_if_exist(room, game)

    async def game_control(self, event):
        # Process event
        room = event.get('room')
        game = self.games[room]
        if event.get('control') == 'start-game':
            game.start()
            await self.db_interface.update_room(room, game.get_num_players(), game.started)
        elif event.get('control') == 'change-seat':
            player = game.get_player_by_name(event.get('player'))
            seat = event.get('value')
            game.player_change_seat(player, seat)
        self.start_move_timer_if_exist(room, game)
        await self._send_frontend_to_players(room, game)
    
    async def disconnect_from_game(self, event):
        """Remove disconnected player from the corresponding game.
        If no player left in the game, remove the game entirely."""
        room = event.get('room')
        game = self.games[room]
        if not game.started:
            game.remove_player(event.get('player'))
            if game.is_empty():
                await self.db_interface.delete_room(room)
                del self.games[room]
            else:
                await self._send_chat_to_players(room, f"{event.get('player')} has left the room")
                await self._send_frontend_to_players(room, game)
                await self.db_interface.update_room(room, game.get_num_players(), game.started)
            logging.info(f"Removed player {event.get('player')} from game {room}")
    
    async def join_game(self, event):
        player = event.get('player')
        room = event.get('room')
        if not room in self.games:
            self.games[room] = CoupGame(room)
            # It's ok if an entry exist, we will update with latest state using update_room
            await self.db_interface.add_room(room)
        game = self.games[room]
        game.add_player(player)

        # Send chat message to clients to inform new player join
        await self._send_chat_to_players(room, f'{player} has joined the room')
        await self._send_frontend_to_players(room, game)
        await self.db_interface.update_room(room, game.get_num_players(), game.started)

    @async_to_sync
    async def make_default_move_and_update(self, room, game):
        logging.info("------ DEFAULT_MOVE")
        game.make_default_moves()
        await self._send_frontend_to_players(room, game)
        self.clear_move_timer(room)
        self.start_move_timer_if_exist(room, game)
    
    def start_move_timer_if_exist(self, room, game):
        dur = game.get_move_timeout()
        if dur:
            self.move_timeout[room] = Timer(dur, self.make_default_move_and_update, [room, game])
            self.move_timeout[room].start()
            logging.info('Timer started')
    
    def clear_move_timer(self, room):
        if self.move_timeout[room]:
            self.move_timeout[room].cancel()
            self.move_timeout[room] = None
            logging.info("Timer cleared")

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
            individual_update[player.name] = {
                'interface': self.coup_frontend.player_interface(game, player),
                'player_view': self.coup_frontend.player_view(game, player)
            }
        await self.channel_layer_sender.broadcast_to_group(room, individual_update)

            
class ChannelLayerMessageSender(object):
    def __init__(self, channel_layer):
        self._channel_layer = channel_layer
    
    async def broadcast_to_group(self, group_name, data):
        logging.debug(f'Broadcasting to {group_name} : {data}')
        await self._channel_layer.group_send(group_name, data)

    async def send_to_consumer(self, consumer_name, data):
        logging.debug(f'Sending to consumer {consumer_name} : {data}')
        await self._channel_layer.send(consumer_name, data)

class RoomManagerToDBInterface(object):
    def __init__(self):
        pass

    @database_sync_to_async
    def load_all_rooms(self):
        return [q.name for q in Room.objects.all()]
    
    @database_sync_to_async
    def reset_database(self):
        for q in Room.objects.all():
            q.delete()

    @database_sync_to_async
    def add_room(self, room_name):
        """Create a room entry in database.
        Returns True if successful, False otherwise"""
        try:
            new_room = Room(name=room_name, password="", num_players=1, game_started=False)
            new_room.save()
        except IntegrityError as ex:
            if "UNIQUE constraint failed" in ex.args[0]:
                logging.info(f"Room {room_name} already exist in database. No new entry added.")
            else:
                logging.error(f"Error occured while trying to create new room: {ex}")
            return False
        except Exception as ex:
            logging.error(f"Error occured while trying to create new room: {ex}")
            return False
        return True
    
    @database_sync_to_async
    def update_room(self, room_name, num_players, game_started):
        """Update the fields of the room with the same name as given in the database
        Returns True if successful, False otherwise"""
        room_queryset = Room.objects.filter(name=room_name)
        if not room_queryset:
            logging.error(f"Room {room_name} not found while attempting to update database")
            return
        assert (len(room_queryset) == 1), "Encountered room with same name"
        room = room_queryset[0]
        room.name = room_name
        room.num_players = num_players
        room.game_started = game_started
        try:
            room.save()
        except Exception as ex:
            logging.error(f"Error occured while trying to update room detail: {ex}")
            return False
        return True
    
    @database_sync_to_async
    def delete_room(self, room_name):
        """Remove the room entry from the database
        Returns True if successful, False otherwise"""
        room_queryset = Room.objects.filter(name=room_name)
        if len(room_queryset) == 0:
            logging.error(f"Room {room_name} not found in attempt to delete entry from database")
            return False
        if len(room_queryset) > 1:
            logging.error(f"Multiple rooms with name: {room_name} found")
            return False
        room_queryset[0].delete()
        return True
