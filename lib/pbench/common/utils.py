"""
Utility functions common to both agent and server.
"""
import hashlib
import ipaddress
import re

from functools import partial


def md5sum(filename: str) -> (int, str):
    """
    md5sum - return the MD5 check-sum of a given file without reading the
             entire file into memory.

    Returns a tuple of the length and the hex digest string of the given file.
    """
    with open(filename, mode="rb") as f:
        d = hashlib.md5()
        length = 0
        for buf in iter(partial(f.read, 2 ** 20), b""):
            length += len(buf)
            d.update(buf)
    return length, d.hexdigest()


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
