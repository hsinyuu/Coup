import enum
class test(enum.Enum):
    CARD_ONE = 'card_one'
    CARD_TWO = 'card_two'


test_list = list()
test_list.append(test.CARD_ONE)
test_list.append(test.CARD_ONE)
test_list.append(test.CARD_ONE)
test_list.append(test.CARD_TWO)
test_list.append(test.CARD_TWO)
test_list.append(test.CARD_TWO)

import pdb; pdb.set_trace()
