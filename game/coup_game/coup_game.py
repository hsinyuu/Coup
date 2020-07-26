import logging
import pprint
import enum
import json
from game.coup_game.objects import CourtDeck
from game.coup_game.player import CoupGamePlayer
from game.coup_game.move import GameMoveFactory
from game.coup_game.turn.turn import CoupGameTurn
from game.coup_game.turn.state import TurnState
import game.coup_game.turn.move_handler as move_handler
import game.coup_game.turn.move_factory as move_factory
from game.coup_game.exceptions import BadGameState, NotEnoughPlayer, SeatOccupied, GameIsFull

"""
Call flow goes like this:
game = CoupGame(room_name)
fe = CoupGameFrontend(game)
game.add_player('bob')
game.add_player('tom')
game.start()
bob = game.get_player_by_name('bob')
move = str_to_move('income')
game.player_make_move(bob, move)
for player in game.players:
    send_back_to_client(fe.game_view(), fe.player_interface(player))
"""

class CoupGameFrontend(object):
    """Define possible frontend interface to the game.
    Frontend is what ultimately gets sent to the client."""
    def __init__(self):
        pass

    def game_view(self, game):
        assert isinstance(game, CoupGame), 'Bad value for game'

        # Get game state and send updates
        game_view = list()
        if not game.started:
            for seat, player in game.player_seats.items():
                seated_player_name = None
                if player:
                    seated_player_name = player.name
                game_view.append({'player':seated_player_name, 'seat': seat})
            return game_view

        for player in game.players:
            cards = list()
            for lost_card in player.lost_influence:
                cards.append(lost_card.value)
            for owned_card in player.owned_influence:
                cards.append('folded')
            game_view.append({
                'player': player.name,
                'seat': None,
                'coins': player.coins,
                'cards': cards,
                'status': 'in_game',
                'turn': game.turn_player == player
            })
        return game_view
        
    def player_interface(self, game, player):
        assert isinstance(game, CoupGame), 'Bad value for game'
        assert isinstance(player, CoupGamePlayer), 'Bad value for player'
        # Get valid moves for player
        if not game.started:
            return []

        interface = dict()
        player_valid_moves = game.get_valid_moves_for_player(player)
        player_valid_moves_serialized = list()
        for move in player_valid_moves:
            player_valid_moves_serialized.append(move.value)
        return player_valid_moves_serialized

class CoupGame(object):
    MAX_NUM_PLAYERS = 6

    def __init__(self, name):
        self.name = name
        self.deck = None
        self.players = list()
        self.player_seats = {seat:None for seat in range(0, self.MAX_NUM_PLAYERS)}
        self.name_to_player = dict()
        self._turn_player_index = None

        # State
        self.started = False
        self.turn = None

    @property
    def turn_player(self):
        return self.players[self._turn_player_index]
    
    def is_game_full(self):
        return self.get_num_players() == self.MAX_NUM_PLAYERS
    
    def get_winner(self):
        players_in_game = [player for player in self.players if player.is_in_game()]
        if not len(players_in_game) == 1:
            return None
        elif len(players_in_game) == 0:
            assert False
        return players_in_game[0]
    
    def next_turn(self):
        """Reset game state and update turn player to the next player in order"""
        self._turn_player_index = (self._turn_player_index+1) % len(self.players)
        if not self.turn_player.is_in_game():
            self._turn_player_index = (self._turn_player_index+1) % len(self.players)
        self.turn.reset_turn(self.turn_player)

        logging.info([n.name for n in self.players])
        logging.info(f'Turn {self._turn_player_index} : {self.turn_player.name}')
    
    def get_num_players(self):
        return len(self.players)
    
    def get_num_seats(self):
        return len(self.player_seats)
    
    def get_player_names(self):
        return [pl.name for pl in self.players]
    
    def get_player_by_name(self, name):
        if name not in self.name_to_player:
            return None
        return self.name_to_player[name]
    
    def get_player_current_seat(self, player):
        for seat, seated_player in self.player_seats.items():
            if player == seated_player:
                return seat
        return None
    
    def add_player(self, player_name, seat=None):
        if player_name in self.name_to_player:
            return None
        
        if self.is_game_full():
            raise GameIsFull(f"Game {self.name} has reached maximum number of players {self.get_num_players()}")

        new_player = CoupGamePlayer(player_name)
        self.players.append(new_player)
        self.name_to_player[player_name] = new_player
        if seat:
            self.player_seats[seat] = new_player
        else:
            # Find the next available seat to place the new player
            for seat, player in self.player_seats.items():
                if not player:
                    self.player_seats[seat] = new_player
                    return new_player
    
    def player_change_seat(self, player, new_seat):
        assert new_seat <= self.get_num_seats(), f"Seat {new_seat} out of bound"
        if self.player_seats[new_seat]:
            raise SeatOccupied

        curr_seat = self.get_player_current_seat(player)
        assert curr_seat is not None, "Error: Expected player to be in a game seat."
        self.player_seats[curr_seat] = None
        self.player_seats[new_seat] = player
    
    def start(self):
        self.deck = CourtDeck()
        self.deck.shuffle()
        for player in self.players:
            player.draw_influence_from_deck(self.deck)
            player.draw_influence_from_deck(self.deck)

        self._turn_player_index = 0
        self.turn = CoupGameTurn(self.turn_player, self.get_num_players(), self.deck)

        if self.get_num_players() < 2:
            raise NotEnoughPlayer(f"Unable to start game with {self.get_num_players()} players")
        self.started = True

    def get_loser_from_challenge(self, player, challenger, challenged_move):
        for influence in player.owned_influence:
            if challenged_move in Influence.doable_action_and_counter(influence):
                logging.info(f"player {player.name}, owned influence {player.owned_influence}, challenged move {challenged_move} won")
                return challenger
        logging.info(f"player {player.name}, owned influence {player.owned_influence}, challenged move {challenged_move} lost")
        return player
    
    def player_make_move(self, player, move, target=None):
        assert isinstance(player, CoupGamePlayer), "Bad value for player"
        if not self.started:
            raise BadGameState(f"Game {self.name} has not started yet")
        move_handler.apply_move_handler(self.turn, player, move, target)
        if self.turn.is_done():
            self.next_turn()
    
    def get_valid_moves_for_player(self, player):
        return move_factory.get_move_for_player(self.turn, player)