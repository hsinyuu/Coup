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
    BLOCK_FOREIGN_AID = 'block-foreign_aid'
    BLOCK_ASSASSINATION = 'block-assassination'
    BLOCK_STEALING = 'block-stealing'

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
        self.turn_player = None
        self.game_state = None

    async def ping(self):
        await self.broadcast_message_to_room(header='chat-message', message='CoupGame ping')
    
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
        self.turn_player = self.players[0]
        self.game_state = 'turn_action'

        # TODO: Change valid number of players to 2
        if self.get_num_players() == 0:
            logging.error("Game engine try to start game but there are no players in the game")
            await self.broadcast_message_to_room(header='chat-message', message='Error: Not enough player.')
            return
        await self.broadcast_message_to_room(header='chat-message', message='Game Start')
        await self.broadcast_game_state()
    
    async def update_game_state(self, event):
        await broadcast_game_state()
        pass
    
    async def broadcast_game_state(self):
        """This function should update player of the current game state"""
        await self.broadcast_message_to_room(header='chat-message', message=self.turn_player.name + '\'s turn')
        message = dict()
        if self.game_state is 'turn_action':
            for player in self.players:
                if player == self.turn_player:
                    message[player.name] = {
                        'header':'player-valid-moves',
                        'message':[action.value for action in Actions]
                    }
                else:
                    message[player.name] = {
                        'header':'player-valid-moves',
                        'message':[]
                    }
        await self.broadcast_game_state_message_to_room(message)
           
        '''
        opponents = [pl for pl in self.players if not pl == self.turn_player]
        action = self.query_action_from_player(self.turn_player)
        challenger = self.query_challenge_from_player_list(opponents)
        loser = get_challenge_loser(player, challenger, action)
        self.lose_influence(loser)
        if not loser == player:
            self.update_game_state(player, action)
            return
        
        counteraction, counter_player = self.query_counter_from_player_list(opponents, action)
        if not counter:
            return
        if self.query_challenge_from_player_list([player])
            loser = get_challenge_loser(counter_player, player, counteraction)
            self.lose_influence(loser)
            if not loser == counter_player:
                self.update_game_state(counter_player, counteraction)
        '''

    async def broadcast_game_state_message_to_room(self, message):
        logging.info(f'CoupGame {self.name} broadcasting {message}')
        await self.channel_layer.group_send(
            self.name, {
                'type': 'game_state_update',
                'message': message
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