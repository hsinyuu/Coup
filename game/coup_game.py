from random import shuffle
import enum

class Actions(enum.Enum):
    INCOME = 'income'
    FOREIGN_AID = 'foreign_aid'
    COUP = 'coup'
    TAX = 'tax'
    ASSASINATE = 'assassinate'
    STEAL = 'steal'
    EXCHANGE = 'exchange'

class Counteractions(enum.Enum):
    BLOCK_FOREIGN_AID = 'block_foreign_aid'
    BLOCK_ASSASSINATION = 'block_assassination'
    BLOCK_STEALING = 'block_stealing'

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
    def __init__(self):
        self.deck = None
        self.players = list()
        self.turn_player = None
        self.game_state = None
    
    def get_num_players(self):
        return len(self.players)
    
    def add_player(self, player_name):
        self.players.append(CoupGamePlayer(player_name))
    
    def start_game(self):
        self.deck = CourtDeck()
        self.deck.shuffle()
        for player in self.players:
            player.draw_influence_from_deck(self.deck)
            player.draw_influence_from_deck(self.deck)
        self.turn_player = self.players[0]
        self.do_turn()
    
    def do_turn(self):
        pass
        '''
        self.get_turn_action(self.turn_player)
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