from django.test import TestCase
from game.coup_game.coup_game import CoupGame, CoupGameFrontend
from game.coup_game.turn.state import TurnState
from game.coup_game.exceptions import NotEnoughPlayer
from game.coup_game.move import Actions, Counteractions, GenericMove
from game.coup_game.objects import Influence

class CoupGameTestCase(TestCase):
    def setUp(self):
        self.game = CoupGame('test')
        self.game.add_player('player0')
        self.game.add_player('player1')
        self.game.add_player('player2')
        self.game.start()
    
    def test_not_enough_player_error(self):
        """Expect NotEnoughPlayer exception if player number is less than 2"""
        game_not_enough_player = CoupGame('test')
        game_not_enough_player.add_player('player0')
        try:
            game_not_enough_player.start()
        except Exception as ex:
            self.assertIsInstance(ex, NotEnoughPlayer)
    
    def test_add_player(self):
        self.assertEqual(self.game.get_player_by_name('player0').name, 'player0')
        self.assertEqual(self.game.get_player_by_name('player1').name, 'player1')
        self.assertEqual(self.game.get_player_by_name('player2').name, 'player2')

    def test_action_income(self):
        turn_player = self.game.turn_player
        self.game.player_make_move(player=turn_player, move=Actions.INCOME, target=None)
        self.assertEqual(turn_player.coins, 1)
        self.assertEqual(self.game.turn.state, TurnState.ACTION)    # Turn should reset
        self.assertNotEqual(self.game.turn_player, turn_player)     # Turn should advance to next round
    
    def test_action_foreign_aid(self):
        turn_player = self.game.turn_player
        opponents = [pl for pl in self.game.players if not pl == turn_player]
        self.game.player_make_move(player=turn_player, move=Actions.FOREIGN_AID, target=None)
        for opp in opponents:
            self.game.player_make_move(player=opp, move=GenericMove.PASS, target=None)
        self.assertEqual(turn_player.coins, 2)
        self.assertEqual(self.game.turn.state, TurnState.ACTION)    # Turn should reset
        self.assertNotEqual(self.game.turn_player, turn_player)     # Turn should advance to next round

    def test_action_tax(self):
        turn_player = self.game.turn_player
        opponents = [pl for pl in self.game.players if not pl == turn_player]
        self.game.player_make_move(player=turn_player, move=Actions.TAX, target=None)
        for opp in opponents:
            self.game.player_make_move(player=opp, move=GenericMove.PASS, target=None)
        self.assertEqual(turn_player.coins, 3)
        self.assertEqual(self.game.turn.state, TurnState.ACTION)    # Turn should reset
        self.assertNotEqual(self.game.turn_player, turn_player)     # Turn should advance to next round

    def test_action_steal(self):
        turn_player = self.game.turn_player
        opponents = [pl for pl in self.game.players if not pl == turn_player]
        target = opponents[0]
        target.coins += 2

        self.game.player_make_move(player=turn_player, move=Actions.STEAL, target=target)
        self.assertEqual(self.game.turn.state, TurnState.ACTION_RESPONSE)

        self.game.player_make_move(player=target, move=GenericMove.PASS, target=None)
        self.assertEqual(turn_player.coins, 2)
        self.assertEqual(target.coins, 0)
        self.assertEqual(self.game.turn.state, TurnState.ACTION)    # Turn should reset
        self.assertNotEqual(self.game.turn_player, turn_player)     # Turn should advance to next round
    
    def test_action_assassinate(self):
        turn_player = self.game.turn_player
        turn_player.coins += 3
        opponents = [pl for pl in self.game.players if not pl == turn_player]
        target = opponents[0]
        influence_to_lose = target.owned_influence[0]

        self.game.player_make_move(player=turn_player, move=Actions.ASSASSINATE, target=target)
        self.assertEqual(self.game.turn.state, TurnState.ACTION_RESPONSE)

        self.game.player_make_move(player=target, move=GenericMove.PASS, target=None)
        self.game.player_make_move(player=target, move=GenericMove.LOSE_INFLUENCE, target=influence_to_lose)
        self.assertIn(influence_to_lose, target.lost_influence)
        self.assertEqual(len(target.owned_influence), 1)
        self.assertEqual(self.game.turn.state, TurnState.ACTION)    # Turn should reset
        self.assertNotEqual(self.game.turn_player, turn_player)     # Turn should advance to next round

    def test_action_coup(self):
        turn_player = self.game.turn_player
        turn_player.coins += 7
        opponents = [pl for pl in self.game.players if not pl == turn_player]
        target = opponents[0]
        influence_to_lose = target.owned_influence[0]

        self.game.player_make_move(player=turn_player, move=Actions.COUP, target=target)
        self.assertEqual(self.game.turn.state, TurnState.LOSE_INFLUENCE)    # Coup cannot be countered. Straight to lose influence state.

        self.game.player_make_move(player=target, move=GenericMove.LOSE_INFLUENCE, target=influence_to_lose)
        self.assertIn(influence_to_lose, target.lost_influence)
        self.assertEqual(len(target.owned_influence), 1)
        self.assertEqual(self.game.turn.state, TurnState.ACTION)    # Turn should reset
        self.assertNotEqual(self.game.turn_player, turn_player)     # Turn should advance to next round

    def test_action_exchange(self):
        # Exchange card is done by adding 2 cards and losing 2 cards
        turn_player = self.game.turn_player
        opponents = [pl for pl in self.game.players if not pl == turn_player]
        exchange_card0 = turn_player.owned_influence[0]
        exchange_card1 = turn_player.owned_influence[1]
        self.game.player_make_move(player=turn_player, move=Actions.EXCHANGE)
        for opp in opponents:
            self.game.player_make_move(player=opp, move=GenericMove.PASS, target=None)
        self.assertEqual(self.game.turn.state, TurnState.EXCHANGE_INFLUENCE)
        self.assertEqual(len(turn_player.owned_influence), 4)
        new_card0 = turn_player.owned_influence[2]
        new_card1 = turn_player.owned_influence[3]
        self.game.player_make_move(player=turn_player, move=GenericMove.DISCARD_INFLUENCE, target=exchange_card0)
        self.game.player_make_move(player=turn_player, move=GenericMove.DISCARD_INFLUENCE, target=exchange_card1)
        self.assertEqual(len(turn_player.owned_influence), 2)
        self.assertIn(new_card0, turn_player.owned_influence)
        self.assertIn(new_card1, turn_player.owned_influence)

    def test_counter_block_foreign_aid(self):
        turn_player = self.game.turn_player
        opponents = [pl for pl in self.game.players if not pl == turn_player]
        opponent = opponents[0]
        self.game.player_make_move(player=turn_player, move=Actions.FOREIGN_AID, target=None)
        self.game.player_make_move(player=opponent, move=Counteractions.BLOCK_FOREIGN_AID, target=None)
        self.assertEqual(self.game.turn.state, TurnState.COUNTER_RESPONSE)    # Turn should reset
        self.game.player_make_move(player=turn_player, move=GenericMove.PASS, target=None)
        self.assertEqual(turn_player.coins, 0)
        self.assertEqual(self.game.turn.state, TurnState.ACTION)    # Turn should reset
        self.assertNotEqual(self.game.turn_player, turn_player)     # Turn should advance to next round

    def test_counter_block_steal(self):
        turn_player = self.game.turn_player
        opponents = [pl for pl in self.game.players if not pl == turn_player]
        target = opponents[0]
        target.coins = 2
        self.game.player_make_move(player=turn_player, move=Actions.STEAL, target=target)
        self.game.player_make_move(player=target, move=Counteractions.BLOCK_STEAL, target=None)
        self.game.player_make_move(player=turn_player, move=GenericMove.PASS, target=None)
        self.assertEqual(turn_player.coins, 0)
        self.assertEqual(self.game.turn.state, TurnState.ACTION)    # Turn should reset
        self.assertNotEqual(self.game.turn_player, turn_player)     # Turn should advance to next round

    def test_counter_block_assassination(self):
        turn_player = self.game.turn_player
        turn_player.coins = 3
        opponents = [pl for pl in self.game.players if not pl == turn_player]
        target = opponents[0]
        self.game.player_make_move(player=turn_player, move=Actions.ASSASSINATE, target=target)
        self.game.player_make_move(player=target, move=Counteractions.BLOCK_ASSASSINATION, target=None)
        self.game.player_make_move(player=turn_player, move=GenericMove.PASS, target=None)
        self.assertEqual(turn_player.coins, 0)
        self.assertEqual(len(target.owned_influence), 2)
        self.assertEqual(self.game.turn.state, TurnState.ACTION)    # Turn should reset
        self.assertNotEqual(self.game.turn_player, turn_player)     # Turn should advance to next round
    
    def test_block_assassination_challenge(self):
        """A more complex case where target challenges assasination without contessa, 
        the target loses two influences."""
        # # Add Assassin to player's hand
        turn_player = self.game.turn_player
        turn_player.coins = 3
        turn_player.owned_influence.pop() 
        turn_player.owned_influence.append(Influence.ASSASSIN)

        # Setup target's hand so that contessa is missing
        opponents = [pl for pl in self.game.players if not pl == turn_player]
        target = opponents[0]
        target.owned_influence.pop()
        target.owned_influence.pop()
        target_inf0 = Influence.CAPTAIN
        target_inf1 = Influence.CAPTAIN
        target.owned_influence.append(target_inf0)
        target.owned_influence.append(target_inf1)

        self.game.player_make_move(player=turn_player, move=Actions.ASSASSINATE, target=target)
        self.game.player_make_move(player=target, move=Counteractions.BLOCK_ASSASSINATION, target=None)
        self.game.player_make_move(player=turn_player, move=GenericMove.CHALLENGE, target=None)

        self.assertEqual(self.game.turn.state, TurnState.LOSE_INFLUENCE)    # Turn should reset
        self.game.player_make_move(player=target, move=GenericMove.LOSE_INFLUENCE, target=target_inf0)
        self.assertEqual(self.game.turn.state, TurnState.LOSE_INFLUENCE)    # Turn should reset
        self.game.player_make_move(player=target, move=GenericMove.LOSE_INFLUENCE, target=target_inf1)

        self.assertEqual(len(target.owned_influence), 0)
        self.assertEqual(self.game.turn.state, TurnState.ACTION)    # Turn should reset
        self.assertNotEqual(self.game.turn_player, turn_player)     # Turn should advance to next round
    
    def test_action_challenge(self):
        turn_player = self.game.turn_player
        turn_player.owned_influence.pop()
        turn_player.owned_influence.append(Influence.DUKE)
        opponents = [pl for pl in self.game.players if not pl == turn_player]
        opponent = opponents[0]
        opponent.owned_influence.pop()
        opponent.owned_influence.append(Influence.DUKE)
        loser = opponent
        influence_to_lose = loser.owned_influence[0]

        self.game.player_make_move(player=turn_player, move=Actions.TAX, target=None)
        self.game.player_make_move(player=opponent, move=GenericMove.CHALLENGE)
        self.assertEqual(self.game.turn.state, TurnState.LOSE_INFLUENCE)
        self.game.player_make_move(player=loser, move=GenericMove.LOSE_INFLUENCE, target=influence_to_lose)
        self.assertIn(influence_to_lose, loser.lost_influence)
        self.assertEqual(len(loser.owned_influence), 1)
    
    def test_counter_challenge(self):
        turn_player = self.game.turn_player
        opponents = [pl for pl in self.game.players if not pl == turn_player]
        opponent = opponents[0]
        opponent.owned_influence.pop()
        opponent.owned_influence.pop()
        opponent.owned_influence.append(Influence.CONTESSA)
        opponent.owned_influence.append(Influence.CONTESSA)
        loser = opponent
        influence_to_lose = loser.owned_influence[0]
        self.game.player_make_move(player=turn_player, move=Actions.FOREIGN_AID, target=None)
        self.game.player_make_move(player=opponent, move=Counteractions.BLOCK_FOREIGN_AID, target=None)
        self.game.player_make_move(player=turn_player, move=GenericMove.CHALLENGE, target=None)
        self.game.player_make_move(player=loser, move=GenericMove.LOSE_INFLUENCE, target=influence_to_lose)
        self.assertIn(influence_to_lose, loser.lost_influence)
        self.assertEqual(len(loser.owned_influence), 1)

    def test_valid_move_action(self):
        turn_player = self.game.turn_player
        opponents = [pl for pl in self.game.players if not pl == turn_player]
        opponent = opponents[0]

        moves = self.game.get_valid_moves_for_player(player=turn_player)
        self.assertCountEqual(moves, [Actions.INCOME, Actions.FOREIGN_AID, Actions.EXCHANGE, Actions.STEAL, Actions.TAX])

        moves = self.game.get_valid_moves_for_player(player=opponent)
        self.assertCountEqual(moves, [])
    
    def test_valid_move_action_response(self):
        turn_player = self.game.turn_player
        opponents = [pl for pl in self.game.players if not pl == turn_player]
        opponent = opponents[0]
        self.game.player_make_move(player=turn_player, move=Actions.FOREIGN_AID, target=None)
        moves = self.game.get_valid_moves_for_player(player=turn_player)
        self.assertCountEqual(moves, [])
        moves = self.game.get_valid_moves_for_player(player=opponent)
        self.assertCountEqual(moves, [Counteractions.BLOCK_FOREIGN_AID, GenericMove.PASS])

    def test_valid_move_counter_response(self):
        turn_player = self.game.turn_player
        opponents = [pl for pl in self.game.players if not pl == turn_player]
        opponent = opponents[0]
        self.game.player_make_move(player=turn_player, move=Actions.FOREIGN_AID, target=None)
        self.game.player_make_move(player=opponent, move=Counteractions.BLOCK_FOREIGN_AID, target=None)
        moves = self.game.get_valid_moves_for_player(player=turn_player)
        self.assertCountEqual(moves, [GenericMove.PASS, GenericMove.CHALLENGE])
        moves = self.game.get_valid_moves_for_player(player=opponent)
        self.assertCountEqual(moves, [])

    def test_valid_move_lose_influence(self):
        turn_player = self.game.turn_player
        opponents = [pl for pl in self.game.players if not pl == turn_player]
        opponent = opponents[0]
        opponent.owned_influence.pop()
        opponent.owned_influence.append(Influence.DUKE)
        self.game.player_make_move(player=turn_player, move=Actions.FOREIGN_AID, target=None)
        self.game.player_make_move(player=opponent, move=Counteractions.BLOCK_FOREIGN_AID, target=None)
        self.game.player_make_move(player=turn_player, move=GenericMove.CHALLENGE, target=None)
        moves = self.game.get_valid_moves_for_player(player=opponent)
        self.assertCountEqual(moves, [])
        moves = self.game.get_valid_moves_for_player(player=turn_player)
        self.assertCountEqual(moves, [GenericMove.LOSE_INFLUENCE,])

    def test_valid_move_assassination_counter_challenge(self):
        turn_player = self.game.turn_player
        turn_player.owned_influence.pop()
        turn_player.owned_influence.append(Influence.ASSASSIN)
        opponents = [pl for pl in self.game.players if not pl == turn_player]
        target = opponents[0]
        target_inf0 = target.owned_influence[0]
        target_inf1 = target.owned_influence[1]
        self.game.player_make_move(player=turn_player, move=Actions.ASSASSINATE, target=target)
        self.game.player_make_move(player=target, move=GenericMove.CHALLENGE, target=None)
        
        moves = self.game.get_valid_moves_for_player(player=target)
        self.assertCountEqual(moves, [GenericMove.LOSE_INFLUENCE,])
        moves = self.game.get_valid_moves_for_player(player=turn_player)
        self.assertCountEqual(moves, [])

        self.game.player_make_move(player=target, move=GenericMove.LOSE_INFLUENCE, target=target_inf0)
        self.game.player_make_move(player=target, move=GenericMove.LOSE_INFLUENCE, target=target_inf1)

        next_turn_player = self.game.turn_player
        moves = self.game.get_valid_moves_for_player(player=next_turn_player)
        self.assertCountEqual(moves, [Actions.INCOME, Actions.FOREIGN_AID, Actions.EXCHANGE, Actions.STEAL, Actions.TAX])

    def test_valid_move_exchange_influence(self):
        turn_player = self.game.turn_player
        opponents = [pl for pl in self.game.players if not pl == turn_player]
        exchange_card0 = turn_player.owned_influence[0]
        exchange_card1 = turn_player.owned_influence[1]

        self.game.player_make_move(player=turn_player, move=Actions.EXCHANGE)
        for opp in opponents:
            moves = self.game.get_valid_moves_for_player(player=opp)
            self.assertCountEqual(moves, [GenericMove.PASS, GenericMove.CHALLENGE])
            self.game.player_make_move(player=opp, move=GenericMove.PASS, target=None)

        new_card0 = turn_player.owned_influence[2]
        new_card1 = turn_player.owned_influence[3]
        moves = self.game.get_valid_moves_for_player(player=turn_player)
        self.assertCountEqual(moves, [GenericMove.DISCARD_INFLUENCE])

        self.game.player_make_move(player=turn_player, move=GenericMove.DISCARD_INFLUENCE, target=exchange_card0)
        moves = self.game.get_valid_moves_for_player(player=turn_player)
        self.assertCountEqual(moves, [GenericMove.DISCARD_INFLUENCE])

        self.game.player_make_move(player=turn_player, move=GenericMove.DISCARD_INFLUENCE, target=exchange_card1)
        moves = self.game.get_valid_moves_for_player(player=turn_player)
        self.assertCountEqual(moves, [])    # No action available once two cards have been exchanged

class FrontendTestCase(TestCase):
    def setUp(self):
        self.game = CoupGame('test')
        self.fe = CoupGameFrontend()
        self.game.add_player('player0')
        self.game.add_player('player1')
        self.game.add_player('player2')
    
    def test_not_started_game_view(self):
        game_view = self.fe.game_view(self.game)
        self.assertEqual(game_view, [
            {'player': 'player0', 'seat': 0}, 
            {'player': 'player1', 'seat': 1}, 
            {'player': 'player2', 'seat': 2}, 
            {'player': None, 'seat': 3}, 
            {'player': None, 'seat': 4}, 
            {'player': None, 'seat': 5}
            ])

        # New player should be added to the next available seat
        self.game.add_player('player3')
        game_view = self.fe.game_view(self.game)
        self.assertEqual(game_view, [
            {'player': 'player0', 'seat': 0}, 
            {'player': 'player1', 'seat': 1}, 
            {'player': 'player2', 'seat': 2}, 
            {'player': 'player3', 'seat': 3}, 
            {'player': None, 'seat': 4}, 
            {'player': None, 'seat': 5}
            ])
    
    def test_change_seat_game_view(self):
        game_view = self.fe.game_view(self.game)
        self.assertEqual(game_view, [
            {'player': 'player0', 'seat': 0}, 
            {'player': 'player1', 'seat': 1}, 
            {'player': 'player2', 'seat': 2}, 
            {'player': None, 'seat': 3}, 
            {'player': None, 'seat': 4}, 
            {'player': None, 'seat': 5}
            ])

        player = self.game.get_player_by_name('player0')
        self.game.player_change_seat(player, 5)
        game_view = self.fe.game_view(self.game)
        self.assertEqual(game_view, [
            {'player': None, 'seat': 0}, 
            {'player': 'player1', 'seat': 1}, 
            {'player': 'player2', 'seat': 2}, 
            {'player': None, 'seat': 3}, 
            {'player': None, 'seat': 4}, 
            {'player': 'player0', 'seat': 5}
            ])

    def test_action_income(self):
        self.game.start()
        turn_player = self.game.turn_player
        game = self.game
        game.player_make_move(player=turn_player, move=Actions.INCOME, target=None)
        game_view = self.fe.game_view(game)
        self.assertEqual(game_view, [
                {'player': 'player0', 'seat': None, 'coins': 1, 'cards': ['folded', 'folded'], 'status': 'in-game', 'turn': False}, 
                {'player': 'player1', 'seat': None, 'coins': 0, 'cards': ['folded', 'folded'], 'status': 'in-game', 'turn': True}, 
                {'player': 'player2', 'seat': None, 'coins': 0, 'cards': ['folded', 'folded'], 'status': 'in-game', 'turn': False}
            ])

        for player in game.players:
            interface = self.fe.player_interface(game, player)
            if player == game.turn_player:
                self.assertEqual(interface, ['income', 'foreign-aid', 'exchange', 'steal', 'tax'])
            else:
                self.assertEqual(interface, [])