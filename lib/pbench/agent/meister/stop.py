import errno
import json
import logging
import os
import signal
import sys
import time

import redis


class StopMixIn:
    def __init__(self, context):
        super(StopMixIn, self).__init__(context)

    def stop(self):
        PROG = os.path.basename(sys.argv[0])
        logger = logging.getLogger(PROG)
        if os.environ.get("_PBENCH_TOOL_MEISTER_STOP_LOG_LEVEL") == "debug":
            log_level = logging.DEBUG
        else:
            log_level = logging.INFO
        logger.setLevel(log_level)
        sh = logging.StreamHandler()
        sh.setLevel(log_level)
        shf = logging.Formatter("%(message)s")
        sh.setFormatter(shf)
        logger.addHandler(sh)

        try:
            benchmark_run_dir = os.environ["benchmark_run_dir"]
        except Exception:
            logger.exception("failed to fetch parameters from the environment")
            return 1

        try:
            redis_server = redis.Redis(host="localhost", port=self.redis_port, db=0)
        except Exception as e:
            logger.error(
                "Unable to connect to redis server, localhost:%d: %r",
                self.redis_port,
                e,
            )
            return 2

        try:
            tm_pids_raw = redis_server.get("tm-pids")
            if tm_pids_raw is None:
                logger.error('Tool Meister PIDs key, "tm-pids", does not exist.')
                return 3
            tm_pids_str = tm_pids_raw.decode("utf-8")
            tm_pids = json.loads(tm_pids_str)
        except Exception as ex:
            logger.error('Unable to fetch and decode "tm-pids" key: %s', ex)
            return 4
        else:
            expected_pids = 0
            if "ds" in tm_pids:
                expected_pids += 1
            if "tm" in tm_pids:
                expected_pids += len(tm_pids["tm"])
            logger.debug("tm_pids = %r", tm_pids)

        ret_val = 0

        logger.debug(
            "terminating %d pids at localhost:%d", expected_pids, self.redis_port
        )
        terminate_msg = dict(action="terminate", group=None, directory=None)
        try:
            num_present = redis_server.publish(
                self.channel, json.dumps(terminate_msg, sort_keys=True)
            )
        except Exception:
            logger.exception("Failed to publish terminate message")
            ret_val = 1
        else:
            if num_present != expected_pids:
                logger.error(
                    "Failed to terminate %d pids, only encountered %d on the channel",
                    expected_pids,
                    num_present,
                )
                ret_val = 1

        # The assumption/assertion here is that the tool meister "stop" command is
        # run on the same node as the tool data sink. So we want to make sure
        # anything "local" to this stop command is shut down gracefully before we
        # report back to the user.  If tool meisters from remote nodes have
        # already reported that they have received the "terminate" message, then
        # we trust they will shutdown gracefully themselves.
        if "ds" in tm_pids:
            pid = tm_pids["ds"]["pid"]
            logger.debug("waiting for tool-data-sink (%d) to exit", pid)
            while self.is_running(pid):
                time.sleep(0.1)
        if "tm" in tm_pids:
            for tm in tm_pids["tm"]:
                if tm["hostname"] == self.full_hostname:
                    pid = tm["pid"]
                    logger.debug("waiting for local tool-meister (%d) to exit", pid)
                    while self.is_running(pid):
                        time.sleep(0.1)

        if ret_val == 0:
            # All was good so far, so we can terminate the redis server.
            try:
                redis_server_pid_file = os.path.join(
                    benchmark_run_dir, "tm", "redis_{:d}.pid".format(self.redis_port)
                )
                try:
                    with open(redis_server_pid_file, "r") as fp:
                        pid_str = fp.read()
                except OSError as exc:
                    if exc.errno != errno.ENOENT:
                        raise
                else:
                    redis_server_pid = int(pid_str)
                    pid_exists = True
                    while pid_exists:
                        try:
                            os.kill(redis_server_pid, signal.SIGTERM)
                        except ProcessLookupError:
                            pid_exists = False
                        else:
                            time.sleep(0.1)
            except Exception:
                logger.exception("Exception encountered terminating Redis server")
                ret_val = 1

        return ret_val

    def is_running(self, pid):
        """Is the given PID running?

        See https://stackoverflow.com/questions/7653178/wait-until-a-certain-process-knowing-the-pid-end
        """
        try:
            os.kill(pid, 0)
        except OSError as err:
            if err.errno == errno.ESRCH:
                return False
        return True
