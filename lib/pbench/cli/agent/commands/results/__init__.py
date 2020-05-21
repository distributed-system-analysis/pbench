import os
import sys
import requests

from pbench.agent import logger
from pbench.agent.config import AgentConfig
from pbench.agent.results import MakeResultTb, CopyResultTb


def move_results(_user, _prefix, _show_server):
    config = AgentConfig()
    config_agent = config.get_agent()
    config_results = config.get_results()
    if not _user:
        _user = config_agent.get("pbench_user")
    pbench_run = config_agent.get("pbench_run")
    if not pbench_run:
        logger.error("No pbench_run configured under pbench-agent section")
        sys.exit(1)
    if not os.path.exists(pbench_run):
        logger.error("pbench local results directory does not exist: %s", pbench_run)
        sys.exit(1)

    controller = os.environ.get("full_hostname")
    if not controller:
        logger.error("Missing controller name (should be 'hostname -f' value)")
        sys.exit(1)

    results_webserver = config_results.get("webserver")
    if not results_webserver:
        logger.error(
            "No web server host configured from which we can fetch the FQDN of the host to which we copy/move results"
        )
        logger.debug("'webserver' variable in 'results' section not set")

    host_info_url = config_results.get("host_info_url")
    server_rest_url = config_results.get("server_rest_url")
    response = requests.get(f"{server_rest_url}/host_info")

    if response.status_code not in [200, 201]:
        logger.error("Unable to determine results host info from %s", host_info_url)
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

    pbench_tmp = os.environ.get("pbench_tmp")
    temp_dir = os.path.join(
        pbench_tmp, ".".join([os.path.basename(__file__), str(os.getpid())]), controller
    )
    try:
        os.makedirs(temp_dir)
    except OSError:
        logger.error("Failed to create temporary directory")
        sys.exit(1)

    dirs = [
        _dir
        for _dir in next(os.walk(pbench_run))[1]
        if not _dir.startswith("tools-") and not _dir.startswith("tmp")
    ]

    for _dir in dirs:
        result_dir = os.path.join(pbench_run, _dir)
        mrt = MakeResultTb(result_dir, temp_dir, _user, _prefix)
        result_tb_name = mrt.make_result_tb()
        if result_tb_name:
            crt = CopyResultTb(result_tb_name, results_path_prefix)
            copy_result = crt.copy_result_tb()
            try:
                os.remove(result_tb_name)
                os.remove(f"{result_tb_name}.md5.check")
            except OSError:
                logger.error(
                    "rm failed to remove %s and its .md5.check file", result_tb_name
                )
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
