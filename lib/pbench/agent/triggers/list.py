class ListMixIn:
    def list(self):
        if not self.pbench_run.exists():
            return 0
        if self.context.group:
            tg_dir = self.tool_group_dir(self.context.group)
            if not tg_dir.exists():
                self.logger.error("bad tool group specified, \"%s\"", self.context.group)
                return 1
            trigger = tg_dir / "__trigger__"
            if trigger.exists():
                print(trigger.read_text().strip())
        else:
            if len(self.groups) == 0:
                self.logger.error("error fetching list of tool groups")
                return 1
            for tg_dir in sorted(self.groups):
                name = tg_dir.name.split("tools-v1-")[1]
                tg_dir = tg_dir / "__trigger__"
                if tg_dir.exists():
                    print("%s: %s" % (name, tg_dir.read_text().strip()))
    
    @property
    def groups(self):
        return [p for p in self.pbench_run.glob('tools-v1-*')]
