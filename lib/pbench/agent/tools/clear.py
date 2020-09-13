from pathlib import Path
import shutil

class ClearMixIn:
    def clear_tools(self):
        tg_dir = self.tool_group_dir(self.context.group)
        if not tg_dir.exists():
            return 1
        if not self.context.remotes:
            self.context.remotes = [p.name for p in self.remotes(tg_dir)]
        for remote in self.context.remotes:
            tg_dir_r = tg_dir / remote
            if not tg_dir_r.exists():
                continue
            if not self.context.name:
                self.context.name = [p.name for p in tg_dir_r.iterdir() if p.name != "__label__" and p.suffix != ".__noinstall__"]
            for name in self.context.name:
                name = Path(f"{tg_dir_r}/{name}")
                noinstall = Path(f"{name}.__noinstall__")
                
                name.unlink()
                if noinstall.exists():
                    noinstall.unlink()
                if name.exists():
                    self.logger.error("Failed to clear tool %s", name)
                else:
                    self.logger.info("Removed \"%s\" from host, \"%s\", in tools group, \"%s\"",
                        name.name, remote, self.context.group)
            tool_files = [p.name for p in tg_dir_r.iterdir()]
            if "__label__" in tool_files:
                label = Path(tg_dir_r, "__label__")
                label.unlink()
                if label.exists():
                    self.logger.error("Failed to remove label for remote %s", tg_dir_r.parent)
                    tool_files = []
            if not any(tg_dir_r.iterdir()):
                self.logger.info("All tools removed from %s", remote)
                try:
                    shutil.rmtree(tg_dir_r)
                except Exception:
                    self.logger.exception("Failed to remove remote directory: %s", tg_dir_r)
                    return 0
