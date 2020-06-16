import logging
import copy
import enum
import json
from random import shuffle
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


class Actions(enum.Enum):
    INCOME = 'income'
    FOREIGN_AID = 'foreign-aid'
    COUP = 'coup'
    TAX = 'tax'
    ASSASSINATE = 'assassinate'
    STEAL = 'steal'
    EXCHANGE = 'exchange'

    @classmethod
    def from_str(cls, string_key):
        return cls[string_key.replace('-','_').upper()]

class Counteractions(enum.Enum):
    BLOCK_FOREIGN_AID = 'block-foreign-aid'
    BLOCK_ASSASSINATION = 'block-assassination'
    BLOCK_STEAL = 'block-steal'

    @classmethod
    def from_str(cls, string_key):
        return cls[string_key.replace('-','_').upper()]

    @classmethod
    def get_counter_from_action(cls, action):
        assert isinstance(action, Actions), type(action)
        if action is Actions.FOREIGN_AID:
            return cls.BLOCK_FOREIGN_AID
        elif action is Actions.ASSASSINATE:
            return cls.BLOCK_ASSASSINATION
        elif action is Actions.STEAL:
            return cls.BLOCK_STEAL
        else:
            # Action has no counter
            return None

class Challenge(enum.Enum):
    CHALLENGE = 'challenge'

    @classmethod
    def from_str(cls, string_key):
        return cls[string_key.upper()]

class Pass(enum.Enum):
    PASS = 'pass'

    @classmethod
    def from_str(cls, string_key):
        return cls[string_key.upper()]

class Influence(enum.Enum):
    DUKE = 'duke'
    CAPTAIN = 'captain'
    ASSASSIN = 'assassin'
    CONTESSA = 'contessa'
    AMBASSADOR = 'ambassador'

    @classmethod
    def from_str(cls, string_key):
        return cls[string_key.replace('-','_').upper()]

    @classmethod
    def get_action_or_counter(cls, influence):
        """Returns a tuple of actions or counteractions that can be performed 
        for the given influence"""
        if influence is Influence.DUKE:
            return (Actions.TAX, Counteractions.BLOCK_FOREIGN_AID,)
        if influence is Influence.ASSASSIN:
            return (Actions.ASSASSINATE,)
        if influence is Influence.CAPTAIN:
            return (Actions.STEAL, Counteractions.BLOCK_STEAL,)
        if influence is Influence.CONTESSA:
            return (Counteractions.BLOCK_ASSASSINATION,)
        if influence is Influence.AMBASSADOR:
            return (Actions.EXCHANGE, Counteractions.BLOCK_STEAL,)
        logging.error(f"No Actions or Counteractions for given influence {influence}")
        return None

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
        self.owned_influence = list()  # Cards faced down
        self.lost_influence = list()   # Cards revealed
    
    def __str__(self):
        return self.name
    
    def draw_influence_from_deck(self, deck):
        self.owned_influence.append(deck.draw())

    def exchange_card(self, influence_to_exchange, influence_to_return, deck):
        assert influence_to_exchange in self.owned_influence, f"Player does not own {influence}"
        self.owned_influence.remove(influence_to_return)
        self.owned_influence.append(influence_to_exchange)
        deck.put_back_and_reshuffle(influence_to_return)

    def lose_influence(self, influence):
        assert influence in self.owned_influence, f"Player does not own {influence}"
        self.owned_influence.remove(influence)
        self.lost_influence.append(influence)
    
    def get_doable_actions(self):
        doable_actions = [Actions.INCOME, Actions.FOREIGN_AID, Actions.EXCHANGE, Actions.STEAL, Actions.TAX]
        if self.coins >= 3:
            doable_actions.append(Actions.ASSASSINATE)
        if self.coins >= 7:
            doable_actions.append(Actions.COUP)
        return doable_actions
    
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
    
    
class CoupGame(object):
    def __init__(self, name):
        self.channel_layer = get_channel_layer()
        self.name = name
        self.deck = None
        self.players = list()
        self.name_to_player = dict()
        self.observers = list() # players that are out of the game becomes observers
        self.game_state = None
        self._turn_player_index = None

    @property
    def turn_player(self):
        return self.players[self._turn_player_index]

    async def ping(self):
        await self.broadcast_message_to_room(header='chat-message', message='CoupGame ping')

    def next_turn(self):
        """Reset game state and update turn player to the next player in order"""
        self._turn_player_index = (self._turn_player_index+1) % len(self.players)
        self.game_state = {
            'turn': self.turn_player,
            'wait': 'action',
            'action_played': None,
            'action_target': None,
            'counter_played': None,
            'counter_player': None,
            'counter_failed': None,
            'lose_influence_target': None,
            'pass': list()
        }
        logging.info([n.name for n in self.players])
        logging.info(f'Turn {self._turn_player_index} : {self.turn_player.name}')
    
    def get_num_players(self):
        return len(self.players)
    
    def get_player_names(self):
        return [pl.name for pl in self.players]
    
    def add_player(self, player_name):
        new_player = CoupGamePlayer(player_name)
        self.players.append(new_player)
        self.name_to_player[player_name] = new_player
    
    async def start_game(self):
        self.deck = CourtDeck()
        self.deck.shuffle()
        logging.info(str(self.deck))
        for player in self.players:
            player.draw_influence_from_deck(self.deck)
            player.draw_influence_from_deck(self.deck)

        self._turn_player_index = 0
        self.game_state = {
            'turn': self.turn_player,
            'wait': 'action',
            'action_played': None,
            'action_target': None,
            'counter_played': None,
            'counter_player': None,
            'counter_failed': None,
            'lose_influence_target': None,
            'pass': list()
        }

        # TODO: Change valid number of players to 2
        if self.get_num_players() == 0:
            logging.error("Game engine try to start game but there are no players in the game")
            await self.broadcast_message_to_room(header='chat-message', message='Error: Not enough player.')
            return
        await self.broadcast_message_to_room(header='chat-message', message='Game Start')
    
    def apply_action_and_next_turn(self, action, player, target=None):
        """Modify state of players involved in an action and update the game state.
        Note. that income action is not dealt here, since it always applies."""
        assert isinstance(action, Actions), "Bad value for action"
        assert isinstance(player, CoupGamePlayer), "Bad value for player"
        if action is Actions.FOREIGN_AID:
            player.coins += 2
            self.next_turn()
        elif action is Actions.TAX:
            player.coins += 3
            self.next_turn()
        elif action is Actions.EXCHANGE:
            raise NotImplementedError
            pass
        elif action is Actions.STEAL:
            assert isinstance(target, CoupGamePlayer), "Bad value for target"
            target.coins -= 2
            player.coins += 2
        elif action is Actions.ASSASSINATE:
            assert isinstance(target, CoupGamePlayer), "Bad value for target"
            player.coins -= 3
            self.game_state['lose_influence_target'] = target
            self.game_state['wait'] = 'lose_influence'
        elif action is Actions.COUP:
            assert isinstance(target, CoupGamePlayer), "Bad value for target"
            player.coins -= 7
            self.game_state['lose_influence_target'] = target
            self.game_state['wait'] = 'lose_influence'
    
    async def update_game_state_with_move(self, player_name, move_type, move, target):
        """
        TODO: implement a enum class for wait states
        wait_states:
            action
            counter_or_challenge
            challenge_counter
            lose_influence
            exchange-influence
        """
        logging.info(f"update_game_state_with_move {player_name} {move_type}, {move}, {target}, current wait {self.game_state['wait']}")
        if self.game_state['wait'] == 'action':
            # Validate state vs incoming action
            if not move_type == 'action':
                logging.error(f"Expected action. Player move {(move_type, move, target)}")
                return
            if self.game_state['action_played']:
                logging.error(f"Duplicate action attempt {self.game_state['action']}, attempted {move}")
                return
            # Income cannot be countered or challenged, so we can directly apply it
            if move == Actions.INCOME.value:
                self.name_to_player[player_name].coins += 1
                self.next_turn()
                return
            self.game_state['action_played'] = Actions.from_str(move)
            self.game_state['wait'] = 'counter_or_challenge'

        elif self.game_state['wait'] == 'counter_or_challenge':
            if move_type == 'counter':
                self.game_state['counter_played'] = Counteractions.from_str(move)
                self.game_state['counter_player'] = self.name_to_player[player_name]
                self.game_state['wait'] = 'challenge_counter'
            elif move_type == 'pass':
                if player_name == self.turn_player.name:
                    logging.error('Error: Turn player shouldn\'t be allowed to send pass request')
                    return
                if player_name in self.game_state['pass']:
                    logging.warning(f'{player_name} issued multiple \'pass\' request')
                    return
                self.game_state['pass'].append(player_name)
                if len(self.game_state['pass']) == self.get_num_players()-1:
                    # No challenges, action is effective
                    self.apply_action_and_next_turn(self.game_state['action_played'], self.game_state['turn'], self.game_state['action_target'])
            elif move_type == 'challenge':
                self.game_state['lose_influence_target'] = self.get_loser_from_challenge(
                                                            self.turn_player, 
                                                            self.name_to_player[player_name], 
                                                            self.game_state['action_played']
                                                        )
                self.game_state['wait'] = 'lose_influence'

        elif self.game_state['wait'] == 'challenge_counter':
            if move_type == 'pass':
                if not player_name == self.turn_player.name:
                    logging.error('Error: Opponent players shouldn\'t be allowed to send pass request')
                # Action ineffective. We can directly go to the next round
                self.next_turn()
            elif move_type == 'challenge':
                self.game_state['lose_influence_target'] = self.get_loser_from_challenge(
                                                            self.game_state['counter_player'], 
                                                            self.turn_player, 
                                                            self.game_state['counter_played']
                                                        )
                self.game_state['wait'] = 'lose_influence'

        elif self.game_state['wait'] == 'lose_influence':
            if not move_type == 'select-influence':
                logging.error(f'Expected select-influence movetype: Player move {(move_type, move, target)}')
            self.name_to_player[player_name].lose_influence(Influence.from_str(move))

            # Counteraction failed, action is effective.
            if self.game_state['lose_influence_target'] == self.game_state['turn']:
                self.apply_action_and_next_turn(self.game_state['action_played'], self.game_state['turn'], self.game_state['action_target'])
            else:
                self.next_turn()

        elif self.game_state['wait'] == 'exchange_influence':
            raise NotImplementedError

        else:
            logging.error(f"Unexpected move type {move_type}")
    
    def get_loser_from_challenge(self, player, challenger, challenged_move):
        for influence in player.owned_influence:
            if challenged_move in Influence.get_action_or_counter(influence):
                logging.info(f"player {player.name}, owned influence {player.owned_influence}, challenged move {challenged_move} won")
                return challenger
        logging.info(f"player {player.name}, owned influence {player.owned_influence}, challenged move {challenged_move} lost")
        return player

    async def broadcast_game_state(self):
        """This function should update client of the current game state"""
        player_moves_msg = dict()
        if self.game_state['wait'] == 'action':
            await self.broadcast_message_to_room(header='chat-message', message=self.turn_player.name + '\'s turn')
            for player in self.players:
                if player == self.turn_player:
                    player_moves_msg[player.name] = {
                        'header':'player-valid-moves',
                        'message':[action.value for action in player.get_doable_actions()]
                    }
                else:
                    player_moves_msg[player.name] = {
                        'header':'player-valid-moves',
                        'message':[]
                    }
        elif self.game_state['wait'] == 'counter_or_challenge':
            assert self.game_state['action_played'], "No action played set"
            counters_and_challenge = [Pass.PASS.value]
            if self.game_state['action_played'] is not Actions.FOREIGN_AID:
                counters_and_challenge.append(Challenge.CHALLENGE.value)
            counter = Counteractions.get_counter_from_action(self.game_state['action_played'])
            if counter:
                counters_and_challenge.append(counter.value)
            
            for player in self.players:
                if player == self.turn_player or player.name in self.game_state['pass']:
                    player_moves_msg[player.name] = {
                        'header':'player-valid-moves',
                        'message':[]
                    }
                else:
                    player_moves_msg[player.name] = {
                        'header':'player-valid-moves',
                        'message':counters_and_challenge
                    }
        elif self.game_state['wait'] == 'challenge_counter':
            for player in self.players:
                if player == self.turn_player:
                    player_moves_msg[player.name] = {
                        'header':'player-valid-moves',
                        'message':[Challenge.CHALLENGE.value, Pass.PASS.value]
                    }
                else:
                    player_moves_msg[player.name] = {
                        'header':'player-valid-moves',
                        'message':[]
                    }
        elif self.game_state['wait'] == 'lose_influence':
            for player in self.players:
                if player == self.game_state['lose_influence_target']:
                    player_moves_msg[player.name] = {
                        'header':'player-influence-query',
                        'message':player.get_influence_in_player_perspective()
                    }
                else:
                    player_moves_msg[player.name] = {
                        'header':'player-valid-moves',
                        'message':[]
                    }

        if not player_moves_msg:
            logging.error("Player state undefined")

        logging.debug(f'CoupGame {self.name} broadcasting game_state:\n{json.dumps(player_moves_msg, indent=4)}')
        await self.channel_layer.group_send(
            self.name, {
                'type': 'game_state_update',
                'message': player_moves_msg
            }
        )
    
    async def broadcast_player_state(self):
        """Broadcast player state message in dict form, where 
        each item is addressed to each player."""
        # Each player-state message should contain:
        #   - name   : name of the player or user
        #   - playing       : true/false if the player is playing or is observer
        #   - influence     : current influence in holding
        #   - coin          : current coin number
        #   - is_self       : is client

        player_states = list()
        for player in self.players:
            player_states.append(
                {
                    'name': player.name,
                    'playing': player.is_in_game(),
                    'influence': player.get_influence_in_opponent_perspective(),
                    'coin': player.coins,
                    'is_self': False
                }
            )
        
        player_states_msg = dict()
        for player in self.players:
            # In the above loop, we represented all influences in opponent's perspective.
            # Here, we replace the owned influence to player's perspective. 
            states_viewed_by_player = copy.deepcopy(player_states)
            # TODO: optimize this O(N) replace
            for state in states_viewed_by_player:
                if state['name'] == player.name:
                    state['influence'] = player.get_influence_in_player_perspective()
                    state['is_self'] = True
            player_states_msg[player.name] = {
                'header': 'player-state-list',
                'message': states_viewed_by_player 
            }

        logging.debug(f'CoupGame {self.name} broadcasting player state:\n {json.dumps(player_states_msg, indent=4)}')
        await self.channel_layer.group_send(
            self.name, {
                'type': 'game_state_update',
                'message': player_states_msg
            }
        )
    
    # Helper function for broadcasting generic message
    async def broadcast_message_to_room(self, header, message):
        logging.debug(f'CoupGame {self.name} broadcasting:\n {header}: {json.dumps(message, indent=4)}')
        await self.channel_layer.group_send(
            self.name, {
                'type': 'game_message',
                'header': header,
                'message': message
            }
        )