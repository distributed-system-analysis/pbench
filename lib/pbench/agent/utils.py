import os
import sys
import pathlib

import six

from pbench.agent.logger import logger

tools_group_prefix = "tools-v1"


def initialize(config):
    """Initialize agent envrionment before running a command

    :param config: a configparser object
    """
    if six.PY2:
        logger.error("python3 is required, either directly or through SCL")
        sys.exit(1)

    pbench_run = pathlib.Path(config.rundir)
    if pbench_run.exists():
        # Its possible to run pbench without root
        # but check to make sure that the rundir is writable
        # before we do anything else
        if os.access(pbench_run, os.W_OK) is not True:
            logger.error("%s is not writable", pbench_run)
            sys.exit(1)
        pbench_tmp = pathlib.Path(pbench_run, "tmp")
        if not pbench_run.exists():
            # the pbench temporary directory is always relative to pbench run
            pbench_tmp.mkdir(parents=True, exists_ok=True)
    else:
        logger.error("the provided pbench run directory %s does not exist.", pbench_run)
        sys.exit(1)
    pbench_install_dir = pathlib.Path(config.installdir)
    if not pbench_install_dir.exists():
        logger.error(
            "pbench installation directory %s does not exist", pbench_install_dir
        )
        sys.exit(1)
