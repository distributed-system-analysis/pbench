import os
import sys
import requests
import tempfile

from pbench.common.logger import get_pbench_logger
from pbench.agent import PbenchAgentConfig
from pbench.agent.results import MakeResultTb, CopyResultTb


def move_results(ctx, _user, _prefix, _show_server):
    config = PbenchAgentConfig(ctx["args"]["config"])
    logger = get_pbench_logger("pbench-move-results", config)

    controller = os.environ.get("full_hostname")
    if not controller:
        logger.error("Missing controller name (should be 'hostname -f' value)")
        sys.exit(1)

    results_webserver = config.results.get("webserver")
    if not results_webserver:
        logger.error(
            "No web server host configured from which we can fetch the FQDN of the host to which we copy/move results"
        )
        logger.debug("'webserver' variable in 'results' section not set")

    if not _user:
        _user = config.agent.get("pbench_user")

    server_rest_url = config.results.get("server_rest_url")
    response = requests.get(f"{server_rest_url}/host_info")
    if response.status_code not in [200, 201]:
        logger.error(
            "Unable to determine results host info from %s/host_info", server_rest_url
        )
        sys.exit(1)
    if response.text.startswith("MESSAGE"):
        message = response.text.split("===")[1]
        logger.info("*** Message from sysadmins of %s:", results_webserver)
        logger.info("***\n*** %s", message)
        logger.info("***\n*** No local actions taken.")
        sys.exit(1)
    results_path_prefix = response.text.split(":")[1]
    if not results_path_prefix:
        logger.error(
            "fetch results host info did not contain a path prefix: %s", response.text
        )
        sys.exit(1)

    runs_copied = 0
    failures = 0

    try:
        temp_dir = tempfile.mkdtemp(
            dir=config.pbench_tmp, prefix="pbench-move-results."
        )
    except Exception:
        logger.error("Failed to create temporary directory")
        sys.exit(1)

    dirs = [
        _dir
        for _dir in next(os.walk(config.pbench_run))[1]
        if not _dir.startswith("tools-") and not _dir.startswith("tmp")
    ]

    for _dir in dirs:
        result_dir = config.pbench_run / _dir
        mrt = MakeResultTb(result_dir, temp_dir, _user, _prefix, config, logger)
        result_tb_name = mrt.make_result_tb()
        if result_tb_name:
            crt = CopyResultTb(controller, result_tb_name, config, logger)
            copy_result = crt.copy_result_tb()
            try:
                os.remove(result_tb_name)
                os.remove(f"{result_tb_name}.md5")
            except OSError:
                logger.error("rm failed to remove %s and its .md5 file", result_tb_name)
                sys.exit(1)
            if not copy_result:
                failures += 1
                continue

            try:
                os.remove(result_dir)
            except OSError:
                logger.error(
                    "rm failed to remove the %s directory hierarchy", result_dir
                )
                sys.exit(1)

            runs_copied += 1

    if runs_copied + failures > 0:
        logger.debug(
            "successfully moved %s runs, encountered %s failures", runs_copied, failures
        )

    return failures
