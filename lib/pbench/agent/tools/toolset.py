from configparser import NoSectionError, NoOptionError
import os


class ToolSetMixIn:
    def __init__(self, context):
        super(ToolSetMixIn, self).__init__(context)

    def toolset(self):
        try:
            the_tool_set = self.config.get(
                "pbench/tools", f"{self.context.toolset}-tool-set"
            )
        except (NoOptionError, NoSectionError):
            self.logger.error(
                "ERROR: failed to fetch tool set, %s-tool-set, from the pbench-agent configuration file",
                self.context.toolset,
            )
            return 1

        if not the_tool_set:
            self.logger.error(
                "ERROR: empty tool set, %s-tool-set, fetched from the pbench-agent configuration file",
                self.conttext.toolset,
            )
            return 1

        if len(self.context.labels_arg) > 0:
            self.context.name = "perf"
            status = self.register_tool()
            if status == 0:
                self.context.remotes_arg = f"(default) {self.full_hostname}"
            self.logger.error(
                'The number of labels given, "%s", does not match the number of remotes given, "%s"',
                self.context.labels_arg,
                self.context.remotes_arg,
            )
            return 1

        nerrors = 0
        reg_perf = 0
        for toolset in the_tool_set.split(","):
            toolset = toolset.strip()
            if toolset == "perf":
                reg_perf = 1
                continue
            try:
                interval = self.config.get(f"tools/{toolset}", "interval")
            except (NoOptionError, NoSectionError):
                interval = self.default_interval

            self.context.name = toolset
            self.context.remotes_arg = os.environ["full_hostname"]
            self.context.tool_opts = f"--interval={interval}"
            status = self.register_tool()
            if status != 0:
                nerrors += 1

        if reg_perf != 0:
            self.context.name = "perf"
            self.context.tool_opts = f"--record-opts=" "record -a --freq=100" ""
            status = self.register_tool()
            if status != 0:
                nerrors += 1

        return nerrors
