from pathlib import Path

import sh

from pbench.agent.utils import run_command


class PostprocessMixIn:
    def process(self):
        tool_group_dir = self.tool_group_dir(self.context.group)
        if not tool_group_dir.exists():
            return 1

        tool_output_dir = Path(f"{self.context.directory}/tools-{self.context.group}")
        if not tool_output_dir.exists():
            self.logger.error(
                '[%s] expected tool output directory, "%s", does not exist',
                self.NAME,
                tool_output_dir,
            )
            return 1

        failures = 0
        for dirent in tool_group_dir.glob("*"):
            if dirent.name == "__trigger__":
                continue
            elif dirent.is_file():
                continue
            host_tool_output_dir = tool_output_dir / dirent.name
            if host_tool_output_dir.exists():
                for filent in dirent.glob("*"):
                    if filent.is_dir() and not filent.is_symlink():
                        # Ignore unrecognized directories or symlinks
                        continue
                    if filent.name == "__label__":
                        continue
                    tool = "{}/tool-scripts/{}".format(
                        self.pbench_install_dir, filent.name
                    )
                    if not Path(tool).exists():
                        continue
                    logfile = open(Path(host_tool_output_dir, "postprocess.log"), "w")
                    result = run_command(
                        sh.Command(tool),
                        "--postprocess",
                        f"--dir={host_tool_output_dir}",
                        out=logfile,
                    )
                    if result.exit_code != 0:
                        print(logfile.read_text())

            else:
                self.logger.warn(
                    "[%s] Missing tool output directory, '%s'",
                    self.NAME,
                    host_tool_output_dir,
                )
                failures += 1

        return failures
