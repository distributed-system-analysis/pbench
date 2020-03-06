class PbenchExceptions(Exception):
    """Base class for exceptions"""
    def __init__(self, message=None):
        self.message = message

    def __str__(self):
        return self.message

class CommandNotImplemented(PbenchExceptions):
    """Raise an exception if command is not implemented yet"""
    def __str__(self):
        return "Command not implemented"
