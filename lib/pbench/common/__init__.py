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
        uri : a URL referencing the service to be waited for
        timeout : integer number of seconds to wait before giving up
                  attempts to connect to the URI

    Raises:
        BadConfig : when the URI is missing the host or when the scheme is
                    missing or unrecognized
        ConnectionRefusedError : after the timeout period has been exhausted
    """
    url = urlparse(uri)
    if not url.hostname:
        raise BadConfig("URI must contain a host name")
    if url.scheme == "https":
        port = 443
    elif url.scheme == "http":
        port = 80
    else:
        raise BadConfig(
            f"URI must include a scheme of 'http' or 'https'; found {url.scheme!r}"
        )
    if url.port:
        port = url.port

    end = time() + timeout
    while True:
        try:
            # The timeout argument to `create_connection()` does not play into
            # the retry logic, see:
            #
            # https://docs.python.org/3.9/library/socket.html#socket.create_connection
            with socket.create_connection((url.hostname, port), timeout=1):
                break
        except ConnectionRefusedError:
            if time() > end:
                raise
            sleep(1)
