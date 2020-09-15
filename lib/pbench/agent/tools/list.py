class ListMixIn:
    def list_tools(self):
        if not self.pbench_run.exists():
            return 1

        if not self.context.group:
            self.context.group = [p.name.split("tools-v1-")[1] for p in self.groups]

        if not self.context.name:
            dirs = {}
            for group in self.context.group:
                dirs[group] = {}
                for path in self.tool_group_dir(group).glob("*/**"):
                    dirs[group][path.name] = [p.name for p in self.tools(path)]
            for k, v in dirs.items():
                print("%s: " % k, ", ".join("{} {}".format(h, t) for h, t in v.items()))
        else:
            groups = []
            for group in self.context.group:
                for path in self.tool_group_dir(group).iterdir():
                    if self.context.name in [p.name for p in self.tools(path)]:
                        if group not in groups:
                            groups.append(group)
            if group:
                print(
                    "tool name: %s groups: %s" % (self.context.name, ", ".join(groups))
                )
