class CoupGamePlayer(object):
    """Entity to maintain player state in the game"""
    def __init__(self, name):
        self.name = name
        self.coins = 0
        self.owned_influence = list()  # Cards faced down
        self.lost_influence = list()   # Cards revealed
    
    def __str__(self):
        return self.name
    
    def draw_influence_from_deck(self, deck):
        self.owned_influence.append(deck.draw())

    def exchange_card(self, old, new, deck):
        assert old in self.owned_influence, f"Player does not own {old}"
        self.owned_influence.remove(old)
        self.owned_influence.append(new)
        deck.put_back_and_reshuffle(old)

    def lose_influence(self, influence):
        assert influence in self.owned_influence, f"Player does not own {influence}"
        self.owned_influence.remove(influence)
        self.lost_influence.append(influence)
    
    def get_influence_in_opponent_perspective(self):
        """Return list of influence in string in the perspective of opponents."""
        # Opponents should only see influence that were lost by the player,
        # we use '*' string to denote folded influence.
        viewed_influence = [{'card':'*', 'state':'folded'}]*len(self.owned_influence)
        viewed_influence.extend([{'card':inf.value, 'state':'revealed'} for inf in self.lost_influence])
        return viewed_influence
    
    def get_influence_in_player_perspective(self):
        """Return list of influence in string in the perspective of the owner."""
        viewed_influence = [{'card':inf.value, 'state': 'folded'} for inf in self.owned_influence]
        viewed_influence.extend([{'card':inf.value, 'state':'revealed'} for inf in self.lost_influence])
        return viewed_influence
    
    def is_in_game(self):
        if self.owned_influence:
            return True
        return False