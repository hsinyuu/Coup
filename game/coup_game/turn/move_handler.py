"""This module defines move handler for each possible turn state.
Move handler updates the turn with move params. We update the
turn based on the current state it' in, as well as the move.
Turn states are assigned with default handler unless overwritten."""

import logging
import re
from collections import namedtuple
from game.coup_game.turn.state import TurnState
from game.coup_game.move import Actions, Counteractions, GenericMove
from game.coup_game.objects import Influence
from game.coup_game.exceptions import BadPlayerMove, BadTurnState

def default_handler(turn, player, move, target):
    raise NotImplementedError
_MOVE_HANDLER = {state:default_handler for state in TurnState}

def register_move_handler(func):
    state_name = re.match(r'handle_move_for_([a-z_]*)', func.__name__).group(1)
    state_to_handle = TurnState(state_name)
    _MOVE_HANDLER[state_to_handle] = func
    logging.info(f"Registered move handler {func.__name__} to handle state {state_to_handle}")

def apply_move_handler(turn, player, move, target):
    try:
        if target:
            logging.info(f"{player} used {move} on {target}")
        else:
            logging.info(f"{player} used {move}")
        _MOVE_HANDLER[turn.state](turn, player, move, target)
    except KeyError as ex:
        logging.error(f"Error: Handler does not exist for state {turn.state}")

# Helper functions
ChallengeResult = namedtuple('ChallengeResult', 'winner loser exchange_card')
def get_challenge_result(player, challenger, challenged_move):
    for influence in player.owned_influence:
        if challenged_move in Influence.doable_action_and_counter(influence):
            logging.info(f"{player.name} owned influence {player.owned_influence}, challenged move {challenged_move} won")
            return ChallengeResult(winner=player, loser=challenger, exchange_card=influence)
    logging.info(f"{player.name} owned influence {player.owned_influence}, challenged move {challenged_move} lost")
    return ChallengeResult(winner=challenger, loser=player, exchange_card=None)

def resolve_challenge(turn, player, challenger, challenged_move):
    result = get_challenge_result(player, challenger, challenged_move)
    if result.exchange_card:
        result.winner.exchange_card(result.exchange_card, turn.court_deck.draw(), turn.court_deck)
    turn.add_challenge_winner_loser(result.winner, result.loser)

# Move handler definition
@register_move_handler
def handle_move_for_wait_action(turn, player, move, target):
    player.coins -= Actions.get_cost(move)

    # Validate
    if not player == turn.action_player:
        raise BadTurnState(f"Expected player {turn.action_player.name} to play, got {player.name} instead")
    if turn.state is not TurnState.ACTION:
        raise BadPlayerMove(f"Attempting to play an action {move} in the wrong turn state {turn.state}")
    if not isinstance(move, Actions):
        raise BadPlayerMove(f"Expected action type, received {type(move)}")
    if turn.action_played:
        raise BadPlayerMove(f"Duplicated action attempt")
    if Actions.is_targetable(move) and not target:
        raise BadPlayerMove(f"Expected a target for action {move}")

    # Update
    turn.action_played = move
    if Actions.is_targetable(move):
        turn.action_target = target
    if Actions.is_challengeable(move) or Actions.is_counterable(move):
        turn.add_pass_option()

    if not Actions.is_counterable(move):
        turn.apply_action_and_update_state()
    else:
        turn.change_state(TurnState.ACTION_RESPONSE)

@register_move_handler
def handle_move_for_wait_action_response(turn, player, move, target):
    # Validate
    # ...

    # Update
    if move is GenericMove.PASS:
        turn.add_passed_player(player)
        if turn.player_all_passed():
            turn.apply_action_and_update_state()
    elif move is GenericMove.CHALLENGE:
        resolve_challenge(turn, turn.action_player, player, turn.action_played)
        turn.change_state(TurnState.LOSE_INFLUENCE)
    elif move in Counteractions:
        # Add counteraction to turn
        if player == turn.action_player:
            raise BadPlayerMove(f"Turn player should not be allowed to issue counter")
        turn.counter_player = player
        turn.counter_played = move
        turn.add_pass_option()
        turn.change_state(TurnState.COUNTER_RESPONSE)

@register_move_handler
def handle_move_for_wait_counter_response(turn, player, move, target):
    # Validate
    if move not in (GenericMove.PASS, GenericMove.CHALLENGE):
        raise BadPlayerMove(f"Player should only be allowed to use pass and challenge. Got {move}")
    if player is not turn.action_player:
        raise BadPlayerMove(f"Player should not be allowed to counter respond")

    # Update
    if move is GenericMove.PASS:
        turn.add_passed_player(player)
        if turn.player_all_passed():
            turn.change_state(TurnState.DONE)
    elif move is GenericMove.CHALLENGE:
        resolve_challenge(turn, turn.counter_player, player, turn.counter_played)
        turn.change_state(TurnState.LOSE_INFLUENCE)

@register_move_handler
def handle_move_for_wait_lose_influence(turn, player, move, target):
    # Validate
    if not isinstance(target, Influence):
        raise BadPlayerMove(f"Bad value for target {target} in state {turn.state}")
    if not move is GenericMove.LOSE_INFLUENCE:
        raise BadPlayerMove(f"Player should only be allowed to lose influence")
    if player is not turn.lose_influence_target and player is not turn.challenge_loser:
        raise BadPlayerMove(f"Player {player.name} should not be allowed to lose influence. " \
                                + f"Challenge loser={turn.challenge_loser} " \
                                + f"Target={turn.lose_influence_target} ")
    # Update
    player.lose_influence(target)
    if player is turn.challenge_loser and not turn.action_applied:
        turn.apply_action_and_update_state()
    else:
        turn.change_state(TurnState.DONE)

@register_move_handler
def handle_move_for_wait_exchange_influence(turn, player, move, target):
    if not isinstance(target, Influence):
        raise BadPlayerMove(f"Bad value for target {target} in state {turn.state}")
    if not move is Actions.EXCHANGE:
        raise BadPlayerMove(f"Player should only be allowed to exchange card")
    if turn.num_cards_to_exchange <= 0:
        raise BadTurnState(f"Turn has shouldn't be in exchange card. No cards to exchange.")

    player.lose_influence(target)
    turn.num_cards_to_exchange -= 1
    if turn.num_cards_to_exchange == 0:
        turn.change_state(TurnState.DONE)