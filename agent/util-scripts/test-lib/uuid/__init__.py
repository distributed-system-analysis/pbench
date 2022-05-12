"""Mock the uuid module's `uuid4()` interface.
"""


class UUID:
    def __init__(self):
        self.hex = "00000000-0000-0000-0000-000000000001"

    def __str__(self):
        return self.hex


def uuid4() -> str:
    return UUID()
