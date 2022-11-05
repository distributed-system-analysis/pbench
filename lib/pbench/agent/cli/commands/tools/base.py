from pbench.agent.base import BaseCommand


class ToolCommand(BaseCommand):
    """Common Tool Class"""

    def __init__(self, context):
        super(ToolCommand, self).__init__(context)

    def remote(self, path):
        """List all remotes in a given path"""
        return sorted([p.name for p in path.iterdir() if p.name != "__trigger__"])

    def tools(self, path):
        """List all tools in a given path"""
        return sorted(
            [
                p.name
                for p in path.iterdir()
                if p.name != "__label__" and p.suffix != ".__noinstall__"
            ]
        )

    @property
    def groups(self):
        """List all groups registered"""
        return sorted(
            [p.name.split("tools-v1-")[1] for p in self.pbench_run.glob("tools-v1-*")]
        )
