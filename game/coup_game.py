import logging
import enum
from random import shuffle
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


class Actions(enum.Enum):
    INCOME = 'income'
    FOREIGN_AID = 'foreign-aid'
    COUP = 'coup'
    TAX = 'tax'
    ASSASINATE = 'assassinate'
    STEAL = 'steal'
    EXCHANGE = 'exchange'

class Counteractions(enum.Enum):
    BLOCK_FOREIGN_AID = 'block-foreign-aid'
    BLOCK_ASSASSINATION = 'block-assassination'
    BLOCK_STEALING = 'block-steal'

class Challenge(enum.Enum):
    CHALLENGE = 'challenge'

class Influence(enum.Enum):
    DUKE = 'duke'
    CAPTAIN = 'captain'
    ASSASSIN = 'assassin'
    CONTESSA = 'contessa'
    AMBASSADOR = 'ambassador'

class CourtDeck(object):
    """Entity class to maintain the current deck state in the game"""
    def __init__(self):
        # Initialize all character cards. 3 cards per character.
        self._deck = list()
        self._deck.extend([Influence.DUKE]*3)
        self._deck.extend([Influence.CAPTAIN]*3)
        self._deck.extend([Influence.ASSASSIN]*3)
        self._deck.extend([Influence.CONTESSA]*3)
        self._deck.extend([Influence.CAPTAIN]*3)

    def __str__(self):
        return str([card.value for card in self._deck])

    def shuffle(self):
        shuffle(self._deck)

    def draw(self):
        '''Pop and return one card from the top of the _deck.
        Returns None if there is not card left in the _deck.'''
        if self._deck:
            return self._deck.pop()
        return None
    
    def put_back_and_reshuffle(self, card):
        assert isinstance(card, Influence), f'Bad value for card {card}'
        self._deck.append(card)
        self.shuffle()

class CoupGamePlayer(object):
    """Entity to maintain player state in the game"""
    def __init__(self, name):
        self.name = name
        self.coins = 0
        self._owned_influence = list()  # Cards faced down
        self._lost_influence = list()   # Cards revealed
    
    def __str__(self):
        return self.name

    def draw_influence_from_deck(self, deck):
        self._owned_influence.append(deck.draw())

    def exchange_card(self, influence_to_exchange, influence_to_return, deck):
        assert influence_to_exchange in self._owned_influence, f"Player does not own {influence}"
        self._owned_influence.remove(influence_to_return)
        self._owned_influence.append(influence_to_exchange)
        deck.put_back_and_reshuffle(influence_to_return)
    
    def lose_influence(self, influence):
        assert influence in self._owned_influence, f"Player does not own {influence}"
        self._owned_influence.remove(influence)
        self._lost_influence.append(influence)
    
    def still_alive(self):
        return self._owned_influence

class CoupGame(object):
    def __init__(self, name):
        self.channel_layer = get_channel_layer()
        self.name = name
        self.deck = None
        self.players = list()
        self.observers = list() # players that are out of the game becomes observers
        self.game_state = None
        self._turn_player_index = None

    async def ping(self):
        await self.broadcast_message_to_room(header='chat-message', message='CoupGame ping')
    
    @property
    def turn_player(self):
        return self.players[self._turn_player_index]

    def next_turn(self):
        """Update turn player to the next player in order"""
        self._turn_player_index = (self._turn_player_index+1) % len(self.players)
    
    def get_num_players(self):
        return len(self.players)
    
    def get_player_names(self):
        return [pl.name for pl in self.players]
    
    def add_player(self, player_name):
        self.players.append(CoupGamePlayer(player_name))
    
    async def start_game(self):
        self.deck = CourtDeck()
        self.deck.shuffle()
        for player in self.players:
            player.draw_influence_from_deck(self.deck)
            player.draw_influence_from_deck(self.deck)

        self._turn_player_index = 0
        self.game_state = {
            'turn': self.turn_player,
            'wait': 'action',
            'action_played': None,
            'action_target': None,
            'counter_played': None
        }

        # TODO: Change valid number of players to 2
        if self.get_num_players() == 0:
            logging.error("Game engine try to start game but there are no players in the game")
            await self.broadcast_message_to_room(header='chat-message', message='Error: Not enough player.')
            return
        await self.broadcast_message_to_room(header='chat-message', message='Game Start')
    
    async def update_game_state_with_move(self, move_type, move, target):
        """
        action
        counter_or_challenge
        challenge_counter
        """
        logging.info(f"update_game_state_with_move {move_type}, {move}, {target}, current wait {self.game_state['wait']}")
        if self.game_state['wait'] == 'action':
            if not move_type == 'action':
                logging.error(f"Expected action. Player move {(move_type, move, target)}")
                return
            if self.game_state['action_played']:
                logging.error(f"Duplicate action attempt {self.game_state['action']}, attempted {move}")
                return
            self.game_state['action_played'] = move
            self.game_state['wait'] = 'counter_or_challenge'
        elif self.game_state['wait'] == 'counter_or_challenge':
            if move_type == 'counter':
                # TODO: validate counter vs action
                self.game_state['counter_played'] = move
                self.game_state['wait'] = 'challenge_counter'
            elif move_type == 'challenge':
                # TODO: resolve challenge, find loser of challenge and lose influence
                # Reset game state
                self.next_turn()
                self.game_state = {
                    'turn': self.turn_player,
                    'wait': 'action',
                    'action_played': None,
                    'action_target': None,
                    'counter_played': None
                }
        elif self.game_state['wait'] == 'challenge_counter':
            if not move_type == 'challenge':
                logging.error(f'Expected challenge: Player move {(move_type, move, target)}')
                return
            # TODO: resolve challenge, find loser of challenge and lose influence
            # Reset game state
            self.next_turn()
            self.game_state = {
                'turn': self.turn_player,
                'wait': 'action',
                'action_played': None,
                'action_target': None,
                'counter_played': None
            }
        else:
            logging.error(f"Unexpected move type {move_type}")
    
    async def broadcast_game_state(self):
        """This function should update player of the current game state"""
        player_state = dict()
        if self.game_state['wait'] == 'action':
            await self.broadcast_message_to_room(header='chat-message', message=self.turn_player.name + '\'s turn')
            for player in self.players:
                if player == self.turn_player:
                    player_state[player.name] = {
                        'header':'player-valid-moves',
                        'message':[action.value for action in Actions]
                    }
                else:
                    player_state[player.name] = {
                        'header':'player-valid-moves',
                        'message':[]
                    }
        elif self.game_state['wait'] == 'counter_or_challenge':
            counters_and_challenge = [counter.value for counter in Counteractions]
            counters_and_challenge.append(Challenge.CHALLENGE.value)
            for player in self.players:
                if player == self.turn_player:
                    player_state[player.name] = {
                        'header':'player-valid-moves',
                        'message':[]
                    }
                else:
                    player_state[player.name] = {
                        'header':'player-valid-moves',
                        'message':counters_and_challenge
                    }
        elif self.game_state['wait'] == 'challenge_counter':
            for player in self.players:
                if player == self.turn_player:
                    player_state[player.name] = {
                        'header':'player-valid-moves',
                        'message':[Challenge.CHALLENGE.value]
                    }
                else:
                    player_state[player.name] = {
                        'header':'player-valid-moves',
                        'message':[]
                    }
        
        if not player_state:
            logging.error("Player state undefined")

        logging.info(f'CoupGame {self.name} broadcasting game_state {player_state}')
        await self.channel_layer.group_send(
            self.name, {
                'type': 'game_state_update',
                'message': player_state
            }
        )
    
    async def broadcast_message_to_room(self, header, message):
        logging.info(f'CoupGame {self.name} broadcasting {header}: {message}')
        await self.channel_layer.group_send(
            self.name, {
                'type': 'game_message',
                'header': header,
                'message': message
            }
        )