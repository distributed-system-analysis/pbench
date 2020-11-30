import os
import requests
import shutil
import sys
import tempfile

from pbench.agent import PbenchAgentConfig
from pbench.agent.results import MakeResultTb, CopyResultTb
from pbench.common.logger import get_pbench_logger


def move_results(ctx, _user, _prefix, _show_server):
    config = PbenchAgentConfig(ctx["args"]["config"])
    logger = get_pbench_logger("pbench", config)

    controller = os.environ.get("_pbench_full_hostname")
    if not controller:
        logger.error("Missing controller name (should be 'hostname -f' value)")
        sys.exit(1)

    results_webserver = config.results.get("webserver")
    if not results_webserver:
        logger.error(
            "No web server host configured from which we can fetch the FQDN of the host to which we copy/move results"
        )
        logger.debug("'webserver' variable in 'results' section not set")

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

    try:
        temp_dir = tempfile.mkdtemp(
            dir=config.pbench_tmp, prefix="pbench-move-results."
        )
    except Exception:
        logger.error("Failed to create temporary directory")
        sys.exit(1)

    runs_copied = 0
    failures = 0

    for dirent in config.pbench_run.iterdir():
        if not dirent.is_dir():
            continue
        if dirent.name.startswith("tools-") or dirent.name == "tmp":
            continue
        result_dir = dirent
        mrt = MakeResultTb(result_dir, temp_dir, _user, _prefix, config, logger)
        result_tb_name = mrt.make_result_tb()
        assert (
            result_tb_name
        ), "Logic bomb!  make_result_tb() always returns a tar ball name"
        crt = CopyResultTb(controller, result_tb_name, config, logger)
        crt.copy_result_tb()
        try:
            # We always remove the constructed tar ball, regardless of success
            # or failure, since we keep the result directory below on failure.
            os.remove(result_tb_name)
            os.remove(f"{result_tb_name}.md5")
        except OSError:
            logger.error("rm failed to remove %s and its .md5 file", result_tb_name)
            sys.exit(1)

        try:
            shutil.rmtree(result_dir)
        except OSError:
            logger.error("rm failed to remove the %s directory hierarchy", result_dir)
            sys.exit(1)

        runs_copied += 1

    if runs_copied + failures > 0:
        logger.debug(
            "successfully moved %s runs, encountered %s failures", runs_copied, failures
        )

    return runs_copied, failures
