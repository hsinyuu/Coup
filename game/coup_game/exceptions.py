class NotEnoughPlayer(Exception):
    def __init__(self, message="Not enough player"):
        super().__init__(message)

class BadGameState(Exception):
    def __init__(self, message="Game is at bad game state"):
        super().__init__(message)

class BadTurnState(Exception):
    def __init__(self, message="Game is at bad turn state"):
        super().__init__(message)

class BadPlayerMove(Exception):
    def __init__(self, message="Received unexpected move at current game state"):
        super().__init__(message)