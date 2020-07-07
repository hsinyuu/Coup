import enum

class TurnState(enum.Enum):
    ACTION = 'wait_action'
    ACTION_RESPONSE = 'wait_action_response'
    COUNTER_RESPONSE = 'wait_counter_response'
    LOSE_INFLUENCE = 'wait_lose_influence'
    EXCHANGE_INFLUENCE = 'wait_exchange_influence'
    DONE = 'done'