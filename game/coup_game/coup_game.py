import logging
import random
import pprint
import enum
import json
from game.coup_game.objects import CourtDeck
from game.coup_game.player import CoupGamePlayer, PlayerStatus
from game.coup_game.move import GameMoveFactory
from game.coup_game.turn.turn import CoupGameTurn
import game.coup_game.turn.move_handler as move_handler
import game.coup_game.turn.move_factory as move_factory
from game.coup_game.exceptions import BadGameState, NotEnoughPlayer, SeatOccupied, GameIsFull, BadPlayerMove

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
        """View of all player's cards and coins."""
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

        for player in game.get_players_in_seating_order():
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
                'status': player.status.value,
                'turn': game.turn_player == player
            })
        return game_view
    
    def player_view(self, game, player):
        """View of the in game player. Contains cards and number of coins."""
        if not game.started:
            return None
        
        cards = list()
        for lost_card in player.lost_influence:
            cards.append({'name': lost_card.value, 'status': 'died'})

        for owned_card in player.owned_influence:
            cards.append({'name': owned_card.value, 'status': 'owned'})

        player_view = {
            'player': player.name,
            'coins': player.coins,
            'cards': cards,
        }
        return player_view

    def player_interface(self, game, player):
        assert isinstance(game, CoupGame), 'Bad value for game'
        assert isinstance(player, CoupGamePlayer), 'Bad value for player'
        # Get valid moves for player
        if not game.started:
            return {
                'valid_moves': [],
                'time': None
            }

        interface = dict()
        player_valid_moves = game.get_valid_moves_for_player(player)
        player_valid_moves_serialized = list()
        return {
            'valid_moves': [move.value for move in player_valid_moves],
            'time': game.get_move_timeout() if player_valid_moves else None
        }
    
class CoupGame(object):
    MAX_NUM_PLAYERS = 6

    def __init__(self, name):
        self.name = name
        self.players = list()
        self.player_seats = {seat:None for seat in range(0, self.MAX_NUM_PLAYERS)}
        self.name_to_player = dict()
        self.reset()
    
    def reset(self):
        self.deck = None
        self._turn_player_index = None

        # State
        self.started = False
        self.finished = False
        self.turn = None

        for pl in self.players:
            pl.reset()

    @property
    def turn_player(self):
        return self.players[self._turn_player_index]
    
    def get_players_in_seating_order(self):
        return [self.player_seats[seat] \
            for seat in range(self.MAX_NUM_PLAYERS) \
                if self.player_seats[seat]]
    
    def is_full(self):
        return self.get_num_players() == self.MAX_NUM_PLAYERS
    
    def is_empty(self):
        return self.get_num_players() == 0
    
    def get_winner(self):
        players_in_game = [player for player in self.players if player.is_in_game()]
        if not len(players_in_game) == 1:
            return None
        elif len(players_in_game) == 0:
            assert False
        return players_in_game[0]
    
    def next_turn(self):
        """Reset game state and update turn player to the next player in order"""
        player_still_playing = False
        for i in range(len(self.players)):
            self._turn_player_index = (self._turn_player_index+1) % len(self.players)
            if self.turn_player.is_in_game():
                player_still_playing = True
                break
        if not player_still_playing:
            raise BadGameState("Cannot find in game player for the next turn")
        self.turn.reset_turn(self.turn_player)

        if self.get_winner():
            self.started = False
            self.finished = True

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
        
        if self.is_full():
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
    
    def remove_player(self, player_name):
        # Remove the player from datastructures
        if player_name not in self.name_to_player:
            return None

        player = self.name_to_player[player_name]

        # Remove the player from seat structure
        for seat, seated_player in self.player_seats.items():
            if seated_player == player:
                self.player_seats[seat] = None
                break

        # Remove from name player lookup
        del self.name_to_player[player_name]

        # Remove from player instance list
        self.players.remove(player)
    
    def player_change_seat(self, player, new_seat):
        assert new_seat <= self.get_num_seats(), f"Seat {new_seat} out of bound"
        if self.player_seats[new_seat]:
            raise SeatOccupied

        curr_seat = self.get_player_current_seat(player)
        assert curr_seat is not None, "Error: Expected player to be in a game seat."
        self.player_seats[curr_seat] = None
        self.player_seats[new_seat] = player
    
    def start(self):
        self.reset()
        self.deck = CourtDeck()
        self.deck.shuffle()
        for player in self.players:
            player.draw_influence_from_deck(self.deck)
            player.draw_influence_from_deck(self.deck)

        self._turn_player_index = 0
        self.turn = CoupGameTurn(self.turn_player, self.players, self.deck)

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
    
    def make_default_moves(self):
        """Keep making default moves for players until the turn is reset"""
        MAX_ITER_FOR_INFINITE_LOOP = 3
        for iter in range(MAX_ITER_FOR_INFINITE_LOOP):
            players_to_make_move = [player for player in self.players if self.get_valid_moves_for_player(player)]
            for player in players_to_make_move:
                if self.make_default_move_for_player(player):
                    return

    def make_default_move_for_player(self, player):
        move_tuple = move_factory.get_default_move_target_tuple_for_player(self.turn, player)
        if not move_tuple:
            return self.turn.is_done()
        default_move, default_target = move_tuple
        logging.info(f"Player {player} {player.get_detail_in_str()}")
        return self.player_make_move(player, default_move, default_target)
    
    def get_move_timeout(self):
        if self.started:
            return 25
        else:
            return None
    
    def player_make_move(self, player, move, target=None):
        """Update turn state with player move and target.
        Returns True if the turn is done and has been reset."""
        assert isinstance(player, CoupGamePlayer), "Bad value for player"
        if not self.started:
            raise BadGameState(f"Game {self.name} has not started yet")
        if isinstance(target, CoupGamePlayer) and not target.is_in_game():
            raise BadPlayerMove(f"Player {target.name} selected as target but not in game")
        move_handler.apply_move_handler(self.turn, self.deck, player, move, target)
        logging.info(f"Current turn state: {self.turn.state}")
        if self.turn.is_done():
            self.next_turn()
            return True
        return False
    
    def get_valid_moves_for_player(self, player):
        return move_factory.get_move_for_player(self.turn, player)