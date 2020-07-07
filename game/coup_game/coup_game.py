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
from game.coup_game.exceptions import BadGameState, BadPlayerMove, BadTurnState, NotEnoughPlayer

class CoupGame(object):
    def __init__(self, name):
        self.name = name
        self.deck = None
        self.players = list()
        self.name_to_player = dict()
        self._turn_player_index = None

        # State
        self.game_state = None
        self.turn = None

    @property
    def turn_player(self):
        return self.players[self._turn_player_index]
    
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
    
    def get_player_names(self):
        return [pl.name for pl in self.players]
    
    def get_player_by_name(self, name):
        return self.name_to_player[name]
    
    def add_player(self, player_name):
        new_player = CoupGamePlayer(player_name)
        self.players.append(new_player)
        self.name_to_player[player_name] = new_player
    
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

    def get_loser_from_challenge(self, player, challenger, challenged_move):
        for influence in player.owned_influence:
            if challenged_move in Influence.doable_action_and_counter(influence):
                logging.info(f"player {player.name}, owned influence {player.owned_influence}, challenged move {challenged_move} won")
                return challenger
        logging.info(f"player {player.name}, owned influence {player.owned_influence}, challenged move {challenged_move} lost")
        return player
    
    def player_make_move(self, player, move, target=None):
        move_handler.apply_move_handler(self.turn, player, move, target)
        if self.turn.is_done():
            self.next_turn()
    
    def get_valid_moves_for_player(self, player):
        return move_factory.get_move_for_player(self.turn, player)