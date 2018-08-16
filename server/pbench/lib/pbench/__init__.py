"""
Simple module level convenience functions.
"""

import os, time, errno


def tstos(ts=None):
    return time.strftime("%Y-%m-%dT%H:%M:%S-%Z", time.localtime(ts))
