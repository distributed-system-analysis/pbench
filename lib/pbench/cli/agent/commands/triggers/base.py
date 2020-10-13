from pbench.cli.agent.commands.tools.base import ToolCommand  # needed for groups, tools


class TriggerCommand(ToolCommand):
    def __init__(self, context):
        super().__init__(context)
