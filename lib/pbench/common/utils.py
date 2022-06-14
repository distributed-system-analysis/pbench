"""
Utility functions common to both agent and server.
"""
from collections import deque
import hashlib
import ipaddress
from logging import Logger
from pathlib import Path
import re
from typing import Callable, Deque, NamedTuple, Union

from functools import partial


class Md5Result(NamedTuple):
    length: int
    md5_hash: str


def md5sum(filename: Union[Path, str]) -> Md5Result:
    """
    Return the MD5 check-sum of a given file without reading the entire file
    into memory.

    Args:
        filename    Filename to hash

    Returns:
        Md5Result tuple containing the length and the hex digest of the file.
    """
    with open(filename, mode="rb") as f:
        d = hashlib.md5()
        length = 0
        for buf in iter(partial(f.read, 2**20), b""):
            length += len(buf)
            d.update(buf)
    return Md5Result(length=length, md5_hash=d.hexdigest())


# Derived from https://stackoverflow.com/questions/106179/regular-expression-to-match-dns-hostname-or-ip-address
# with a few modifications: take advantage of ignoring case; use non-capturing
# groups to improve efficiency; take advantage of RFC 1123 modification to RFC
# 952 relaxing first character to be letter or digit, with the repetition moved
# to the last group to alleviate backtracking.  Or in other words, a case-blind
# comparison seeking a letter-or-digit, optionally followed by a sequence of 0
# to 61 letter-or-digit-or-hyphens followed by a letter-or-digit, follwed by 0
# or more instances of that same pattern preceded by a period.
_allowed = re.compile(
    r"[A-Z0-9](?:[A-Z0-9\-]{0,61}[A-Z0-9])?(?:\.[A-Z0-9](?:[A-Z0-9\-]{0,61}[A-Z0-9])?)*",
    flags=re.IGNORECASE,
)


def validate_hostname(host_name: str) -> int:
    """validate_hostname - validate the given hostname uses the proper syntax.

    A host name that follows RFC 952 (amended by RFC 1123) is accepted only.
    Host names are not resolved to IP addresses, and IP addresses are also
    accepted.

    Algorithm taken from: https://stackoverflow.com/questions/2532053/validate-a-hostname-string

    Returns 0 on success, 1 on failure.
    """
    if not host_name or len(host_name) > 255:
        return 1

    if _allowed.fullmatch(host_name):
        return 0

    # It is not a valid host name, but could be a valid IP address.
    try:
        ipaddress.ip_address(host_name)
    except ValueError:
        return 1

    return 0


class CleanupNotCallable(Exception):
    """
    Signal that caller tried to register a cleanup action with an object that
    was not a Callable on an object.
    """

    def __init__(self, action):
        self.action = action

    def __str__(self) -> str:
        return f"Parameter {self.action!r} ({type(self.action)} is not a Callable"


# Following are a set of classes to perform hierarchical cleanup actions when
# an error occurs.
#
# A Deque supports an ordered list of cleanup actions that will be popped and
# executed in reverse order on demand.
#
# Cleanup actions are Callable objects; to queue an action requiring parameters
# a `lambda` expression can be used.


class CleanupAction:
    """
    Define a single cleanup action necessary to reverse persistent steps in an
    operation.
    """

    def __init__(self, logger: Logger, action: Callable, name: str = None):
        """
        Define a cleanup action

        Args:
            logger: The active Pbench Logger object
            action: a Callable to perform cleanup
            name: optional printable name for debugging
        """
        self.action = action
        self.logger = logger
        self.name = name if name else repr(action)

    def cleanup(self):
        """
        Perform a cleanup action, executing a callable associated with some
        object (usually a Dataset or a Path) that needs cleaning.

        This handles errors and reports them, but doesn't propagate failure to
        ensure that cleanup continues as best we can.
        """
        try:
            self.action()
        except Exception:
            # TODO: f-string used because this is shared by agent and server
            self.logger.exception(f"Unable to {self}")

    def __str__(self) -> str:
        return self.name


class Cleanup:
    """
    Maintain and process a deque of cleanup actions accumulated during a
    sequence of steps that need to be reversed or otherwise cleaned up when
    an error condition occurs: for example, shutting down subprocesses,
    deleting directories or object instances.

    Cleanup actions are maintained in an ordered list and will be processed
    in reverse of the order they were registered.

    For example,

        cleanup = Cleanup(logger)
        try:
            [...]
            file = Path(name).mkdir()
            cleanup.add(file.unlink, "Remove file")
            [...]
            cleanup.add(object.delete, "Delete Object")
            [...]
        except Exception:
            cleanup.cleanup()
    """

    def __init__(self, logger: Logger):
        """
        Define a deque on which cleanup actions will be recorded, and attach
        a Pbench Logger object to report errors.

        Args:
            logger: Pbench Logger
        """
        self.logger = logger
        self.actions: Deque[CleanupAction] = deque()

    def add(self, action: Callable, name: str = None) -> None:
        """
        Add a new cleanup action to the front of the deque.

        This registers a Callable that requires no parameters; for example
        `dataset.delete`, or `lambda : del foo["bar"]`

        Args:
            Callable to be executed to clean up a step
        """
        if not callable(action):
            raise CleanupNotCallable(action)
        self.actions.appendleft(CleanupAction(self.logger, action, name))

    def cleanup(self):
        """
        Perform queued cleanup actions in order from most recent to oldest.
        """
        for action in self.actions:
            action.cleanup()


def canonicalize(nt: NamedTuple) -> str:
    """A string containing a deterministic representation of a NamedTuple

    Convert the field names to dict keys, produce them in sorted order, and
    render their object values.  For most field types, this is done in the
    usual way by Python.  In the case of object references, use the object's
    __str__() method if it has one other than the one inherited from the
    fundamental "object" (that prints the object's address, which varies
    from run to run).  For other objects, print out the object's class name.
    If anything goes wrong, produce a default value.
    """
    ret_val = {}
    for k, v in sorted(nt._asdict().items()):
        try:
            if isinstance(
                v, (dict, list, tuple, str, int, float, complex, bool, type(None))
            ):
                ret_val[k] = v
            elif v.__class__.__str__ != object.__str__:
                ret_val[k] = str(v)
            else:
                ret_val[k] = f"<{v.__class__.__name__} object>"
        except Exception:
            ret_val[k] = "<unexpected thing>"
    return str(ret_val)
