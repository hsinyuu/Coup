from game.coup_game.turn.state import TurnState
from game.coup_game.move import Actions, Counteractions, GenericMove
from game.coup_game.exceptions import BadPlayerMove, BadTurnState

class CoupGameTurn(object):
    """Class to represent state variables of the current turn"""
    SAME_STATE_CHANGE_LIMIT = 3
    def __init__(self, turn_player, players, court_deck):
        self.players = players
        self.court_deck = court_deck
        self.reset_turn(turn_player)
        
    def is_done(self):
        return self.state is TurnState.DONE
    
    def change_state(self, state):
        if state == self.state:
            self.change_same_state_cnt += 1
            if self.change_same_state_cnt == self.SAME_STATE_CHANGE_LIMIT:
                raise BadTurnState(f"Changing to the same state {state}")
        self.state = state

    def reset_turn(self, turn_player):
        self.state = TurnState.ACTION
        self.change_same_state_cnt= 0
        # Action
        self.action_player = turn_player
        self.action_played = None
        self.action_target = None
        self.action_applied = False
        self.lose_influence_target = None
        # Counter
        self.counter_played = None
        self.counter_player = None
        # Challenge
        self.challenged = False
        self.challenge_loser = None
        self.challenge_winner = None
        # Exchang
        self.exchange_player = None
        self.num_cards_to_exchange = 0
        # Pass
        self.pass_player_wait_cnt = None
        self.passed_players = None

    def player_passed(self, player):
        return player in self.passed_players
    
    def player_all_passed(self):
        return self.pass_player_wait_cnt == 0

    def add_passed_player(self, player):
        self.pass_player_wait_cnt -= 1
        self.passed_players.append(player)

    def add_lose_influence_player(self, player):
        self.lose_influence_target = player
    
    def add_challenge_winner_loser(self, winner, loser):
        self.lose_influence_target = loser
        self.challenge_loser = loser
        self.challenge_winner = winner
    
    def apply_action_and_update_state(self):
        """Modify state of players involved in an action and update the game state.
        Returns: Current state. If state turn is complete, return None."""
        action = self.action_played
        player = self.action_player
        target = self.action_target
        if action is Actions.INCOME:
            player.coins += 1
            self.change_state(TurnState.DONE)
        elif action is Actions.FOREIGN_AID:
            player.coins += 2
            self.change_state(TurnState.DONE)
        elif action is Actions.TAX:
            player.coins += 3
            self.change_state(TurnState.DONE)
        elif action is Actions.EXCHANGE:
            player.owned_influence.append(self.court_deck.draw())
            player.owned_influence.append(self.court_deck.draw())
            self.num_cards_to_exchange = 2
            self.change_state(TurnState.EXCHANGE_INFLUENCE)
        elif action is Actions.STEAL:
            assert target, f"Expected target for action {action}"
            steal_amount = min(target.coins, 2) # We can steal a max of 2 coins
            target.coins -= steal_amount
            player.coins += steal_amount
            self.change_state(TurnState.DONE)
        elif action is Actions.ASSASSINATE:
            assert target, f"Expected target for action {action}"
            self.add_lose_influence_player(target)
            self.change_state(TurnState.LOSE_INFLUENCE)
        elif action is Actions.COUP:
            assert target, f"Expected target for action {action}"
            self.add_lose_influence_player(target)
            self.change_state(TurnState.LOSE_INFLUENCE)
        self.action_applied = True
    
    def add_pass_option(self):
        # Only need target to pass if targeted action
        # or if action is countered, and we are waiting for turn player 
        self.passed_players = list()
        if self.action_target or self.counter_played:
            self.pass_player_wait_cnt = 1
        else:
            self.pass_player_wait_cnt = len([pl for pl in self.players if pl.is_in_game()]) - 1

    def __str__(self):
        return pprint.pformat({
                'action_player': self.action_player,
                'action_played': self.action_played,
                'action_target': self.action_target,
                'counter_played': self.counter_played,
                'counter_player': self.counter_player,
                'lose_influence_target': self.lose_influence_target,
                'pass_player_wait_cnt': self.pass_player_wait_cnt,
                'state': self.state
            }, indent=4)