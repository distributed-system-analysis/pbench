"""Optional Gunicorn configuration file to enable profiling

This module provides definitions for the pre-request and post-request Gunicorn
hooks, which allow us to get control before a request begins executing and
after it completes.  We use these to enable and disable profiling (so that the
profile reflects only the single method call, with a minimum of extraneous
execution), and, when the request is complete, we dump the profiling report to
a file or to the log.

This file is specified via a command line switch on the Gunicorn invocation
when profiling is requested, and it is read by Gunicorn to set the
`pre_request` and `post_request` Gunicorn settings to the hook routines
defined below.
"""

import cProfile
from io import StringIO
import os
import pstats
import time

from gunicorn.http import Request
from gunicorn.workers import base


def pre_request(worker: base.Worker, req: Request):
    """Gunicorn hook function called before a request is executed

    We create a profile context, notify the log that we're profiling (so that
    no one is surprised), note the current time, and enable Python profiling.
    (We hang the profile context and time stamp off the existing Gunicorn
    worker object (ain't Python grand!?), and we use the worker's log.)
    """
    worker.profile = cProfile.Profile()
    worker.log.info(f"PROFILING {worker.pid}: {req.uri}")
    worker.start_time = time.time()
    worker.profile.enable()


def post_request(worker: base.Worker, req: Request, *_args):
    """Gunicorn hook function called after a request is executed

    Disable Python profiling; calculate the elapsed time for the request
    execution and log it; dump the statistics to a file, or create a pstats
    object which prints its output to a string-stream, sort the stats and print
    them to the stream, and dump the contents of the stream to the log.  (We
    pull the profile context and start time from where we hung them off the
    Gunicorn worker object (ain't Python grand!?), and we use the worker's log.)
    """
    worker.profile.disable()

    total_time = time.time() - worker.start_time
    worker.log.info(
        f"\n[{worker.pid}] [INFO] [{req.method}] Load Time: {total_time:.3}s URI {req.uri}"
    )

    # If PB_PROFILE_DUMP_FILE is defined to a true-y value, assume that it is a
    # file into which to dump the profile data.  (An excellent choice is
    # "/srv/pbench/public_html/pbench_server.prof", because this is writable
    # by the server and easily accessed by the user via the browser by hitting
    # "https://<server>/pbench_server.prof".)  Otherwise, dump the top functions
    # in the profile to the log.  (Note that, if PB_PROFILE_DUMP_FILE is
    # undefined, profiling will not have been enabled, and we'll never get here.)
    dump_file = os.environ.get("PB_PROFILE_DUMP_FILE")
    if dump_file:
        # Note that this will overwrite the previous request's data, if any.
        worker.profile.dump_stats(dump_file)
    else:
        s = StringIO()
        ps = pstats.Stats(worker.profile, stream=s).sort_stats("cumulative")
        ps.print_stats(30)  # Limit the number of lines output
        worker.log.info(f"[{worker.pid}] [INFO] {s.getvalue()}")
