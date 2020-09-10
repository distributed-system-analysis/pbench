import json
import logging
import os
import sys

import daemon
import pidfile
import redis

from pbench.agent.meister import Terminate, ToolMeister


class MeisterMixIn:
    def __init__(self, context):
        super(MeisterMixIn, self).__init__(context)

    def meister(self):
        """Main program for the Tool Meister.

        This function is the simple driver for the tool meister behaviors,
        handling argument processing, logging setup, initial connection to
        Redis(), fetch and validation of operational paramters from Redis(), and
        then the daemonization of the ToolMeister operation.

        Arguments:  argv - a list of parameters

        Returns 0 on success, > 0 when an error occurs.

        """
        PROG = os.path.basename(sys.argv[0])

        logger = logging.getLogger(PROG)
        fh = logging.FileHandler(f"{self.context.param_key}.log")
        if os.environ.get("_PBENCH_UNIT_TESTS"):
            fmtstr = "%(levelname)s %(name)s %(funcName)s -- %(message)s"
        else:
            fmtstr = (
                "%(asctime)s %(levelname)s %(process)s %(thread)s"
                " %(name)s %(funcName)s %(lineno)d -- %(message)s"
            )
        fhf = logging.Formatter(fmtstr)
        fh.setFormatter(fhf)
        if os.environ.get("_PBENCH_TOOL_MEISTER_LOG_LEVEL") == "debug":
            log_level = logging.DEBUG
        else:
            log_level = logging.INFO
        fh.setLevel(log_level)
        logger.addHandler(fh)
        logger.setLevel(log_level)

        try:
            redis_server = redis.Redis(
                host=self.context.redis_host, port=self.context.redis_port, db=0
            )
        except Exception as e:
            logger.error(
                "Unable to construct Redis client, %s:%s: %s",
                self.context.redis_host,
                self.context.redis_port,
                e,
            )
            return 3

        try:
            params_raw = redis_server.get(self.context.param_key)
            if params_raw is None:
                logger.error(
                    'Parameter key, "%s" does not exist.', self.context.param_key
                )
                return 4
            logger.info("params_key (%s): %r", self.context.param_key, params_raw)
            params_str = params_raw.decode("utf-8")
            params = json.loads(params_str)
            # Validate the tool meister parameters without constructing an object
            # just yet, as we want to make sure we can talk to the redis server
            # before we go through the trouble of daemonizing below.
            ToolMeister.fetch_params(params)
        except Exception as exc:
            logger.error(
                "Unable to fetch and decode parameter key, '%s': %s",
                self.context.param_key,
                exc,
            )
            return 5
        else:
            redis_server.connection_pool.disconnect()
            del redis_server

        # Before we daemonize, flush any data written to stdout or stderr.
        sys.stderr.flush()
        sys.stdout.flush()

        ret_val = 0
        pidfile_name = f"{self.context.param_key}.pid"
        pfctx = pidfile.PIDFile(pidfile_name)
        with open(f"{self.context.param_key}.out", "w") as sofp, open(
            f"{self.context.param_key}.err", "w"
        ) as sefp, daemon.DaemonContext(
            stdout=sofp,
            stderr=sefp,
            working_directory=os.getcwd(),
            umask=0o022,
            pidfile=pfctx,
            files_preserve=[fh.stream.fileno()],
        ):
            try:
                # Previously we validated the tool meister parameters, and in
                # doing so made sure we had proper access to the redis server.
                #
                # We can safely create the ToolMeister object now that we are
                # "daemonized".
                logger.debug("constructing Redis() object")
                try:
                    # NOTE: we have to recreate the connection to the redis
                    # service since all open file descriptors were closed as part
                    # of the daemonizing process.
                    redis_server = redis.Redis(
                        host=self.context.redis_host, port=self.context.redis_port, db=0
                    )
                except Exception as e:
                    logger.error(
                        "Unable to connect to redis server, %s:%s: %s",
                        self.context.redis_host,
                        self.context.redis_port,
                        e,
                    )
                    return 6
                else:
                    logger.debug("constructed Redis() object")

                # FIXME: we should establish signal handlers that do the following:
                #   a. handle graceful termination (TERM, INT, QUIT)
                #   b. log operational state (HUP maybe?)

                try:
                    tm = ToolMeister(
                        self.pbench_install_dir, params, redis_server, logger
                    )
                except Exception:
                    logger.exception(
                        "Unable to construct the ToolMeister object with params, %r",
                        params,
                    )
                    return 7

                terminate = False
                try:
                    while not terminate:
                        try:
                            logger.debug("waiting ...")
                            action, data = tm.wait_for_command()
                            logger.debug("acting ... %r, %r", action, data)
                            failures = action(data)
                            if failures > 0:
                                logger.warning(
                                    "%d failures encountered for action, %r,"
                                    " on data, %r",
                                    failures,
                                    action,
                                    data,
                                )
                        except Terminate:
                            logger.info("terminating")
                            terminate = True
                except Exception:
                    logger.exception("Unexpected error encountered")
                    ret_val = 8
                finally:
                    tm.cleanup()
            finally:
                logger.info("Remove pid file ... (%s)", pidfile_name)
                try:
                    os.unlink(pidfile_name)
                except Exception:
                    logger.exception("Failed to remove pid file %s", pidfile_name)

        return ret_val
