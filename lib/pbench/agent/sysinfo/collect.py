from pathlib import Path

import click


class CollectMixIn:
    def collect(self):
        if self.context.options:
            print("default, none, all, %s" % ", ".join(self.sysinfo_opts_available))
            return 0

        if self.context.check:
            self.logger.info(
                "[%s]: sysinfo option is set to %s", self.NAME, self.context.sysinfo
            )
            if self.context.sysinfo in ["all", "default", "none"]:
                pass
            else:
                for item in self.context.sysinfo.split(","):
                    if item in self.sysinfo_opts_available:
                        continue
                    else:
                        if item in ["all", "default", "none"]:
                            continue  # Ignore these options in a list
                        else:
                            self.logger.error('invalid sysinfo option, "%s"', item)
                            return 1

            return 0

        if self.context.sysinfo == "all":
            self.context.sysinfo = self.sysinfo_opts_available_comma_separated
        if self.context.sysinfo == "default":
            self.context.sysinfo = self.sysinfo_opts_default_comma_separated

        if self.context.name != "beg" and self.context.name != "end":
            self.logger.error(
                'Invalid argument, collection names should be either "beg" or "end", not "%s"',
                self.context.name,
            )
            return 1
        click.secho("Collecting system information")

        tool_group_dir = self.tool_group_dir(self.context.group)
        if not tool_group_dir.exists():
            return 1

        self.sysinfo_path = Path(self.context.dir, f"sysinfo/{self.context.name}")
        if self.sysinfo_path.exists():
            self.logger.warn(
                "Already collected sysinfo-dump data, named: %s; skipping...",
                self.context.name,
            )
            return 1
        self.sysinfo_path.mkdir(parents=True)
        if not self.sysinfo_path.exists():
            self.logger.error(
                "Unable to create sysinfo-dump directory base path: %s",
                self.sysinfo_path,
            )
            return 1
        for p in tool_group_dir.iterdir():
            self.label = p / "__label__"
            if p.name in [self.hostname, self.full_hostname]:
                self.dump()

    def dump(self):

        if self.label.exists():
            label = self.label.read_text()
            self.context.dir = Path(self.context.dir, f"{label}:{self.hostname}")
        else:
            self.context.dir = Path(self.context.dir, self.hostname)
        self.context.dir.mkdir(parents=True)
        if not self.context.dir.exists():
            self.logger.error(
                'Failed to create the sysinfo directory, "%s"', self.context.dir
            )
            return 1

        for item in self.context.sysinfo.split(","):
            try:
                self.sysinfo[item]()
            except KeyError:
                self.logger.error("bad")
