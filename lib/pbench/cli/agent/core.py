"""
Base classes for various agent cli commands

Base classes are used so that code can be shared between the same type
of commands without duplicating the same code everywhere.
"""

from pbench.agent.base import BaseCommand


class ToolCommand(BaseCommand):
    """Common tool command Class"""

    def __init__(self, context):
        super().__init__(context)


class LogCommand(BaseCommand):
    """Common logging command class"""

    def __init__(self, context):
        super().__init__(context)


class SysInfoCommand(BaseCommand):
    """Common sysinfo command class"""

    def __init__(self, context):
        super().__init__(context)


class TriggersCommand(BaseCommand):
    """Common Triggers command class"""

    def __init__(self, context):
        super().__init__(BaseCommand)


class ToolMeisterCommand(BaseCommand):
    """Common ToolMeister command class"""

    def __init__(self, context):
        super().__init__(BaseCommand)


class ResultsCommand(BaseCommand):
    """Common Results command class"""

    def __init__(self, context):
        super().__init__(BaseCommand)
