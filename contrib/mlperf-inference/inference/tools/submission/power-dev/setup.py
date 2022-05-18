#!/usr/bin/env python3
from distutils.core import setup
from distutils.command.install_scripts import install_scripts
import os


class custom_install_scripts(install_scripts):
    def run(self):
        install_scripts.run(self)
        for file in self.get_outputs():
            if file.endswith("check.py"):
                new_name = os.path.join(os.path.dirname(file), "power_check")
                os.rename(file, new_name)
                file = new_name
            if os.name == "nt":
                with open(file, "rt") as f:
                    shebang = f.readline()
                    if not shebang.startswith("#!"):
                        continue
                with open(file + ".bat", "wt") as f:
                    f.write(
                        f"@set path=%~dp0\n"
                        f"@set script=%path%{os.path.basename(file)}\n"
                        f"@set /p shebang=<%script%\n"
                        f"@set py=%shebang:~2%\n"
                        f"call %py% %script% %*\n"
                    )


setup(
    name="mlcommons-power",
    version="1.1",
    author="The MLPerf Authors",
    packages=[
        "ptd_client_server",
        "ptd_client_server.lib",
        "ptd_client_server.lib.external",
        "ptd_client_server.tests.unit",
    ],
    scripts=[
        "bin/power_server",
        "bin/power_client",
        "compliance/check.py",
        "compliance/sources_checksums.json",  # has to be in the same directory
    ],
    url="https://github.com/mlcommons/power-dev/",
    license="LICENSE.md",
    description="MLPerf Power Measurement",
    install_requires=['pywin32;platform_system=="Windows"'],
    cmdclass={"install_scripts": custom_install_scripts},
)
