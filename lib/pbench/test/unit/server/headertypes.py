from enum import Enum


class HeaderTypes(Enum):
    VALID = 1
    VALID_ADMIN = 2
    INVALID = 3
    EMPTY = 4

    @classmethod
    def is_valid(self, header):
        return header in [HeaderTypes.VALID, HeaderTypes.VALID_ADMIN]
