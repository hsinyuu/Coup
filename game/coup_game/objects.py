import enum
from random import shuffle
from game.coup_game.move import Actions, Counteractions

class Influence(enum.Enum):
    DUKE = 'duke'
    CAPTAIN = 'captain'
    CONTESSA = 'contessa'
    ASSASSIN = 'assassin'
    AMBASSADOR = 'ambassador'

    @classmethod
    def doable_action_and_counter(cls, influence):
        if influence is cls.DUKE:
            return (Actions.TAX, Counteractions.BLOCK_FOREIGN_AID)
        if influence is cls.CAPTAIN:
            return (Actions.STEAL, Counteractions.BLOCK_STEAL)
        if influence is cls.CONTESSA:
            return (Counteractions.BLOCK_ASSASSINATION,)
        if influence is cls.ASSASSIN:
            return (Actions.ASSASSINATE,)
        if influence is cls.AMBASSADOR:
            return (Actions.EXCHANGE, Counteractions.BLOCK_STEAL)
        raise ValueError(f"Unexpected influence {influence}")

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