"""
Simple module level convenience functions.
"""

import os, time, errno


def tstos(ts=None):
    return time.strftime("%Y-%m-%dT%H:%M:%S-%Z", time.localtime(ts))


def mkdirp(path):
    """
    Create a directory, returning True if it was actually created, False
    otherwise. An exception will be raised for any other condition.
    """
    try:
        os.makedirs(path)
    except OSError as err:
        if err.errno != errno.EEXIST:
            raise
        ret_val = False
    else:
        ret_val = True
    return ret_val


def setup_log_files(env, prog, ts_dir=None):
    """
    Construct the log file directory for an optionally given time stamp
    directory (UTC assumed), and return a tuple of the open files for stdout
    and stderr, and the final timestamp directory that was used (returns the
    same timestamp value if it was provided).
    """
    if not ts_dir:
        ts_dir = "run-%s" % tstos()
    logs_path = os.path.join(env.pubhtml_path, 'logs', ts_dir)
    try:
        os.mkdir(logs_path)
    except OSError as exc:
        if exc.errno != errno.EEXIST:
            raise
    latest_path = os.path.join(env.pubhtml_path, 'logs', "latest")
    try:
        os.unlink(latest_path)
    except OSError as exc:
        if exc.errno != errno.ENOENT:
            raise
    os.symlink(os.path.basename(logs_path), latest_path)
    stderr = open(os.path.join(logs_path, prog + '.errors'), 'w')
    try:
        stdout = open(os.path.join(logs_path, prog + '.log'), 'w')
    except Exception:
        stderr.close()
        raise
    return stdout, stderr, ts_dir
