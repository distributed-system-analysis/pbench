from pathlib import Path


class RegisterMixIn:
    def register_tool(self):
        if not (self.pbench_install_dir / f"tool-scripts/{self.context.name}").exists():
            self.logger.error(
                "Could not find %s in %s/tool-scripts/: has this tool been integrated into the pbench-agent?",
                self.context.name,
                self.pbench_install_dir,
            )
            return 1

        if self.context.remotes_arg.startswith("@"):
            if self.context.labels_arg:
                self.logger.error(
                    "--labels=%s not allowed with remotes file (%s)",
                    self.context.labels_arg,
                    self.context.remotes_arg,
                )
                return 1
            remotes_file = Path(self.context.remotes_arg.split("@")[1])
            remotes = [n for n in remotes_file.read_text().splitlines()]

            remote = {}
            for index, hosts in enumerate(remotes):
                if hosts and not hosts.startswith("#"):
                    count = hosts.count(",")
                    if count == 0:
                        remote.update({hosts: None})
                    elif count == 1:
                        host, label = hosts.split(",")
                        remote.update({host: label})
                    elif count >= 2:
                        self.logger.error(
                            '--remotes=@%s contains an invalid file format, expected lines with "<hostname>[,<label>]" at line #%s',
                            remotes_file,
                            index,
                        )
                        return 1
        else:
            if not self.context.remotes_arg:
                self.logger.error(
                    "INTERNAL: missing -r|--remote|--remotes=<remote-host>[,<remote-host>] argument for some unknown reason (should not happen)"
                )
                return 1

            if self.context.labels_arg:
                self.context.remotes_arg = self.context.remotes_arg.split(",")
                self.context.labels_arg = self.context.labels_arg.split(",")
                if not len(self.context.remotes_arg) == len(self.context.labels_arg):
                    # We emit an error message now if we
                    # are not working on behalf of
                    # pbench-register-tool-set, since it
                    # will handle its own error message on
                    # failure.
                    self.logger.error(
                        'The number of labels given, "%s", does not match the number of remotes given, "%s"',
                        ",".join(self.context.labels_arg),
                        ",".join(self.context.remotes_arg),
                    )
                    return 1
                remotes = dict(zip(self.context.remotes_arg, self.context.labels_arg))
            else:
                remotes = {
                    remote: None for remote in self.context.remotes_arg.split(",")
                }

        tg_dir = self.tool_group_dir(self.context.group)
        tg_dir.mkdir(parents=True, exist_ok=True)
        if not tg_dir.exists():
            self.logger.error(
                "Unable to create the necessary tools group directory, %s", tg_dir
            )
            return 1

        for remote, label in remotes.items():
            if remote == "localhost":
                continue

            tg_dir_r = Path(tg_dir, remote)
            tg_dir_r.mkdir(parents=True, exist_ok=True)
            if tg_dir_r.exists():
                tool_file = Path(tg_dir_r, self.context.name)

                tool_file.touch()
                if self.context.tool_opts:
                    with open(tool_file, "w") as f:
                        f.write("%s\n" % self.context.tool_opts)
                if self.context.noinstall:
                    tool_install = Path(tg_dir_r, f"{self.context.name}.__noinstall__")
                    if tool_install.exists():
                        tool_install.unlink()
                    Path(tool_install).symlink_to(tool_file)

                label_msg = ""
                if label:
                    _label = Path(tg_dir_r, "__label__")
                    if _label.exists():
                        _label.unlink()
                    _label.write_text("%s\n" % label)
                    label_msg = f', with label "{label}"'
                self.logger.info(
                    '"%s" tool is now registered for host "%s"%s in group "%s"',
                    self.context.name,
                    remote,
                    label_msg,
                    self.context.group,
                )
        return 0
