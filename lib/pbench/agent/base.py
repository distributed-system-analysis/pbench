import abc


class BaseCommand(metaclass=abc.ABCMeta):
    """A base class used to define the command interface."""

    def __init__(self, context):
        self.context = context

    @abc.abstractclassmethod
    def execute(self):
        """
        This is the main method of the application.
        """
        pass
