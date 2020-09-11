from pathlib import Path

import click


class RegisterMixIn:
    def register(self):
        trigger = Path(self.tool_group_dir(self.context.group), "__trigger__")
        if trigger.exists():
            trigger.unlink()
        trigger.write_text("%s:%s\n" % (self.context.start, self.context.stop))
        click.secho(f"tool trigger strings for start: \"{self.context.start}\" and for stop: \"{self.context.stop}\""
                    f" are now registered for tool group: \"{self.context.group}\"")