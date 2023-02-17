import configparser
import socket
from time import sleep, time
from urllib.parse import urlparse

from pbench.common.exceptions import BadConfig


class MetadataLog(configparser.ConfigParser):
    """MetadataLog - a sub-class of ConfigParser that always has interpolation
    turned off with no other behavioral changes.
    """

    def __init__(self, *args, **kwargs):
        """Constructor - overrides `interpolation` to always be None."""
        kwargs["interpolation"] = None
        super().__init__(*args, **kwargs)


def wait_for_uri(uri: str, timeout: int):
    """Wait for the given URI to become available.

    While we encounter "connection refused", sleep one second, and then try
    again.

    Args:
        timeout : integer number of seconds to wait before giving up
                  attempts to connect to the URI

    Raises:
        BadConfig : when the URI does not contain either a host or port
        ConnectionRefusedError : after the timeout period has been exhausted
    """
    url = urlparse(uri)
    if not url.hostname:
        raise BadConfig("URI must contain a host name")
    if not url.port:
        raise BadConfig("URI must contain a port number")
    end = time() + timeout
    while True:
        try:
            # The timeout argument to `create_connection()` does not play into
            # the retry logic, see:
            #
            # https://docs.python.org/3.9/library/socket.html#socket.create_connection
            with socket.create_connection((url.hostname, url.port), timeout=1):
                break
        except ConnectionRefusedError:
            if time() > end:
                raise
            sleep(1)
