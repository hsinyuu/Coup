import enum
class PlayerStatus(enum.Enum):
    DEAD = 'dead'
    IN_GAME = 'in-game'

class CoupGamePlayer(object):
    """Entity to maintain player state in the game"""
    def __init__(self, name):
        self.name = name
        self.reset()

    def reset(self):
        self.coins = 0
        self.status = PlayerStatus.IN_GAME
        self.owned_influence = list()  # Cards faced down
        self.lost_influence = list()   # Cards revealed
    
    def draw_influence_from_deck(self, deck):
        self.owned_influence.append(deck.draw())

    def exchange_card(self, old, new, deck):
        assert old in self.owned_influence, f"Player does not own {old}"
        self.owned_influence.remove(old)
        self.owned_influence.append(new)
        deck.put_back_and_reshuffle(old)
    
    def discard_card(self, card, deck):
        assert card in self.owned_influence, f"Player does not own {card}"
        self.owned_influence.remove(card)
        deck.put_back_and_reshuffle(card)

    def lose_influence(self, influence):
        assert influence in self.owned_influence, f"Player does not own {influence}"
        self.owned_influence.remove(influence)
        self.lost_influence.append(influence)
        if not self.owned_influence:
            self.status = PlayerStatus.DEAD

    def is_in_game(self):
        return self.status is PlayerStatus.IN_GAME

    def __str__(self):
        return self.name
    