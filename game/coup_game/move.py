import enum

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
    
    @classmethod
    def is_counterable(cls, action):
        if action in (cls.INCOME, cls.COUP):
            return False
        return True
        
    @classmethod
    def is_challengeable(cls, action):
        return True
    
    @classmethod
    def is_targetable(cls, action):
        return action in (cls.ASSASSINATE, cls.COUP, cls.STEAL)
    
    @classmethod
    def get_cost(cls, action):
        if action is cls.ASSASSINATE:
            return 3
        if action is cls.COUP:
            return 7
        return 0
    
class Counteractions(enum.Enum):
    BLOCK_FOREIGN_AID = 'block-foreign-aid'
    BLOCK_ASSASSINATION = 'block-assassination'
    BLOCK_STEAL = 'block-steal'

    @classmethod
    def from_str(cls, string_key):
        return cls[string_key.replace('-','_').upper()]

    @classmethod
    def is_challengeable(cls, action):
        return True

    def from_action(self, action):
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

class GenericMove(enum.Enum):
    PASS = 'pass'
    CHALLENGE = 'challenge'
    LOSE_INFLUENCE = 'lose_influence'

    @classmethod
    def from_str(cls, string_key):
        return cls[string_key.upper()]
    
class Challenge(enum.Enum):
    CHALLENGE = 'challenge'

    @classmethod
    def from_str(cls, string_key):
        return cls[string_key.upper()]
    
    @classmethod
    def from_action_or_counter(cls, action_or_counter):
        if action_or_counter is Actions.INCOME:
            return None
        return cls.CHALLENGE

class Pass(enum.Enum):
    PASS = 'pass'

    @classmethod
    def from_str(cls, string_key):
        return cls[string_key.upper()]
    
class Control(enum.Enum):
    START_GAME = 'start_game'
    RESTART_GAME = 'restart_game'

    @classmethod
    def from_str(cls, string_key):
        return cls[string_key.upper()]

class GameMoveFactory(object):
    """This is a static class that lays out the rules of action to counteractions"""
    @classmethod
    def counter_from_action(cls, action):
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

    @classmethod
    def challenge_from_action(cls, action):
        if action_or_counter is Actions.INCOME:
            return None
        return GenericMove.CHALLENGE

    @classmethod
    def response_moves_from_action(cls, action):
        def _append_if_exist(list_of_items, item):
            if item:
                list_of_items.append(item)

        response_moves = [GenericMove.PASS] # We can always pass after an action
        _append_if_exist(self.counter_from_action(action))
        _append_if_exsit(self.challenge_from_action(action))
        return response_moves
    
    @classmethod
    def response_moves_from_counter(cls, counter):
        return [GenericMove.CHALLENGE, GenericMove.PASS]
    
    @classmethod
    def actions_from_coins(cls, coins):
        """Get doable actions given the number of coins"""
        doable_actions = [Actions.INCOME, Actions.FOREIGN_AID, Actions.EXCHANGE, Actions.STEAL, Actions.TAX]
        if coins >= 3:
            doable_actions.append(Actions.ASSASSINATE)
        if coins >= 7:
            doable_actions.append(Actions.COUP)
        return doable_actions