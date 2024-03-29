"""This is an usecase module for turn, turn state and possible
moves entities. This module implements move generation for each 
turn state. Each generator should define possible moves for a 
player in a turn state.
To define a turn state move generator, define function with
name 'get_move_for_<state name>', and add register_move_getter 
decorator to the function."""

import logging
import re
from game.coup_game.turn.state import TurnState
from game.coup_game.move import Actions, Counteractions, GenericMove

def default_getter(turn, player):
    raise NotImplementedError
_MOVE_GETTER = {state:default_getter for state in TurnState}

def register_move_getter(func):
    state_name = re.match(r'get_move_for_([a-z_]*)', func.__name__).group(1)
    state_to_handle = TurnState(state_name)
    _MOVE_GETTER[state_to_handle] = func
    logging.info(f"Registered move generator {func.__name__} to for state {state_to_handle}")

def get_move_for_player(turn, player):
    if not player.is_in_game():
        return []
    try:
        return _MOVE_GETTER[turn.state](turn, player)
    except KeyError as ex:
        logging.error(f"Error: Handler does not exist for state {turn.state}")

def get_default_move_target_tuple_for_player(turn, player):
    """Returns a tuple of default move and target for the given player"""
    valid_moves = get_move_for_player(turn, player)
    if not valid_moves:
        return None
    if Actions.INCOME in valid_moves:
        return (Actions.INCOME, None)
    if Actions.COUP in valid_moves:
        opponents = [pl for pl in turn.players if pl != player]
        return (Actions.COUP, opponents[0])
    if GenericMove.LOSE_INFLUENCE in valid_moves:
        assert player.owned_influence, f"Attempt to lose influence but player {player} has no influence"
        return (GenericMove.LOSE_INFLUENCE, player.owned_influence[0])
    if GenericMove.DISCARD_INFLUENCE in valid_moves:
        assert player.owned_influence, f"Attempt to discard influence but player {player} has no influence"
        return (GenericMove.DISCARD_INFLUENCE, player.owned_influence[0])
    logging.warning("Unexpected case while making default move")
    return (valid_moves[0], None)

# Move factory definition
@register_move_getter
def get_move_for_wait_action(turn, player):
    if player == turn.action_player:
        return GameMoveFactory.actions_from_coins(player.coins)
    return []

@register_move_getter
def get_move_for_wait_action_response(turn, player):
    if player == turn.action_player:
        return []
    if player == turn.action_target or not turn.player_passed(player):
        return GameMoveFactory.response_moves_from_action(turn.action_played)
    return []

@register_move_getter
def get_move_for_wait_counter_response(turn, player):
    if player == turn.action_player:
        return GameMoveFactory.response_moves_from_counter(turn.counter_played)
    return []

@register_move_getter
def get_move_for_wait_lose_influence(turn, player):
    if player == turn.lose_influence_target:
        return [GenericMove.LOSE_INFLUENCE,]
    return []

@register_move_getter
def get_move_for_wait_exchange_influence(turn, player):
    if player == turn.action_player:
        return [GenericMove.DISCARD_INFLUENCE,]
    return []

class GameMoveFactory(object):
    """This is a static class that describes the rules of action to counteractions"""
    @classmethod
    def counter_from_action(cls, action):
        assert isinstance(action, Actions), type(action)
        if action is Actions.FOREIGN_AID:
            return Counteractions.BLOCK_FOREIGN_AID
        elif action is Actions.ASSASSINATE:
            return Counteractions.BLOCK_ASSASSINATION
        elif action is Actions.STEAL:
            return Counteractions.BLOCK_STEAL
        else:
            # Action has no counter
            return None

    @classmethod
    def challenge_from_action(cls, action):
        if action in (Actions.INCOME, Actions.FOREIGN_AID):
            return None
        return GenericMove.CHALLENGE

    @classmethod
    def response_moves_from_action(cls, action):
        def _append_if_exist(list_of_items, item):
            if item:
                list_of_items.append(item)

        response_moves = [GenericMove.PASS] # We can always pass after an action
        _append_if_exist(response_moves, cls.counter_from_action(action))
        _append_if_exist(response_moves, cls.challenge_from_action(action))
        return response_moves
    
    @classmethod
    def response_moves_from_counter(cls, counter):
        return [GenericMove.CHALLENGE, GenericMove.PASS]
    
    @classmethod
    def actions_from_coins(cls, coins):
        """Get doable actions given the number of coins"""
        # Can only use coup if the player has 10 or above num coins
        if coins >= 10:
            return [Actions.COUP]

        doable_actions = [Actions.INCOME, Actions.FOREIGN_AID, Actions.EXCHANGE, Actions.STEAL, Actions.TAX]
        if coins >= 3:
            doable_actions.append(Actions.ASSASSINATE)
        if coins >= 7:
            doable_actions.append(Actions.COUP)
        return doable_actions