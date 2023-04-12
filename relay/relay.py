import errno
import functools
from hashlib import sha256
from http import HTTPStatus
import logging
import os
from pathlib import Path
import shutil
import subprocess
from typing import Callable

from bottle import Bottle, HTTPResponse, request, static_file
import click
import humanize

# Keys to Click's command context metadata dictionary for our context values
CTX_SECRET = __name__ + ".secret"
CTX_DIRECTORY = __name__ + ".directory"

# Default values for command options
DEFAULT_ADDRESS = "0.0.0.0"
DEFAULT_PORT = 8080
DEFAULT_FILES_DIRECTORY = "/var/tmp"

FILE_MAX_SIZE = 200 * 1024 * 1024 * 1024  # Maximum file size in bytes: 200Gb
READ_CHUNK_SIZE = 65536  # File upload read chunk size

# Set up logging and create the Bottle application
logging.basicConfig(format="[%(levelname)s] relay: %(message)s", level=logging.DEBUG)
app = Bottle()


def get_disk_utilization_str(dir_path: Path) -> str:
    usage = shutil.disk_usage(dir_path)
    return "{:.3}% full, {} remaining".format(
        float(usage.used) / float(usage.total) * 100.0,
        humanize.naturalsize(usage.free),
    )


def validate_secret(func: Callable) -> Callable:
    """Function decorator for REST API methods which validates the relay secret

    This decorator wraps the supplied API method callback with a function which
    checks that the secret is valid before calling the method.

    Args:
        func: the API method route callback function

    Returns:
        A function which validates the secret, calls the provided method
        callback function, and returns the value that it returns.
    """

    @functools.wraps(func)
    def do_validation(secret: str, *args, **kwargs) -> HTTPResponse:
        """Wrapper function which validates the relay secret

        If the "secret" (i.e., the first URI path parameter, which is the first
        component in the API route) matches the deployment configuration, then
        invoke the API method function and return its result; otherwise
        return a FORBIDDEN response instead of calling the API method.

        The secret argument is omitted from the call to the method, since it is
        only used for validation.

        Args:
            secret:  the contents of the first URI path parameter
            All other arguments are passed through to the API method callback.

        Returns:
            If the secret is valid, returns the response returned by the wrapped
            method function; otherwise, returns a FORBIDDEN response (or, as a
            special case, returns NOT_FOUND if the request is for the favicon).
        """
        if secret == click.get_current_context().meta[CTX_SECRET]:
            return func(*args, **kwargs)

        # Special case this request which seems to come from testing with the
        # browser, just to quiet the noise.
        if secret == "favicon.ico":
            return HTTPResponse(status=HTTPStatus.NOT_FOUND)

        logging.warning(
            'Secret validation failed:  expected "%s", got "%s"',
            click.get_current_context().meta[CTX_SECRET],
            secret,
        )
        return HTTPResponse(status=HTTPStatus.FORBIDDEN)

    return do_validation


@app.get("/<secret>")
@validate_secret
@click.pass_context
def relay_status(context: click.Context) -> HTTPResponse:
    """Relay server status API

    Args:
        context:  the Click context object
                    - for access to the local files directory path

    Returns:
        An HTTP response with a status of OK and a JSON payload containing
        status information (currently, the output from `ls` listing the files
        in the upload directory).
    """
    logging.info("request to report status")
    body = {"disk utilization": get_disk_utilization_str(context.meta[CTX_DIRECTORY])}

    cp = subprocess.run(
        ["ls", "-l"], cwd=context.meta[CTX_DIRECTORY], capture_output=True, text=True
    )
    if cp.returncode:
        body["error"] = cp.stderr.strip()
    else:
        body["files"] = cp.stdout.strip().split("\n")

    return HTTPResponse(status=HTTPStatus.OK, body=body)


@app.delete("/<secret>")
@validate_secret
def shutdown() -> HTTPResponse:
    """Shut down the relay server

    By default, Bottle runs the server until the user types Ctrl-C at the
    terminal; however, neither raising KeyboardInterrupt nor using os.kill()
    in a method callback actually results in an exit (the latter is mapped to
    the former which then gets caught).  It might have something to do either
    with the signal coming from the wrong thread or with it arriving _during_
    the handling of a request.  (Calling exit() didn't work either -- that's
    implemented as an exception, too, apparently.)  So, we need to send the
    signal from outside the process, but using subproccess.run() doesn't work:
    the signal interrupts the function's select(2) call as it waits for the
    subprocess.  However, os.posix_spawn(), which creates an independent
    process, seems to work!  (Note that the response is sent before the server
    shuts down.)
    """
    logging.info("request to shut down")
    os.posix_spawn("/usr/bin/kill", ("DIE.DIE.DIE", "-INT", str(os.getpid())), {})
    return HTTPResponse(status=HTTPStatus.OK, body="Good bye!")


@app.get("/<secret>/<file_id>")
@validate_secret
@click.pass_context
def retrieve_file(context: click.Context, file_id: str) -> HTTPResponse:
    """Send the requested file to the requester

    Args:
        context:  the Click context object
                    - for access to the local files directory path
        file_id:  the SHA256 hash of the file to be retrieved

    Returns:
        An HTTP response indicating the success of the download
    """
    logging.info('request to send file id "%s"', file_id)
    return static_file(file_id, root=context.meta[CTX_DIRECTORY])


@app.put("/<secret>/<file_id>")
@validate_secret
@click.pass_context
def receive_file(context: click.Context, file_id: str) -> HTTPResponse:
    """Receive the file sent by the requester

    The file is uploaded and saved if it does not already exist locally, then
    its SHA256 hash is calculated and compared to the file ID used in the
    request.  If the match fails, the file is deleted and an error is returned.

    Args:
        context:  the Click context object
                    - for access to the local files directory path
        file_id:  the SHA256 hash of the file to be retrieved

    Returns:
        An HTTP response indicating the success of the upload
    """
    logging.info(
        'request to upload file id "%s", disk %s',
        file_id,
        get_disk_utilization_str(context.meta[CTX_DIRECTORY]),
    )

    if not 0 < request.content_length <= FILE_MAX_SIZE:
        return HTTPResponse(
            status=HTTPStatus.BAD_REQUEST,
            body=f"Content-Length ({request.content_length}) "
            f"must be greater than zero and less than {FILE_MAX_SIZE}.",
        )

    remove_file = False
    bytes_remaining = request.content_length
    hash_sha256 = sha256()
    target: Path = context.meta[CTX_DIRECTORY] / file_id
    try:
        with target.open(mode="xb") as ofp:
            while bytes_remaining:
                chunk = request["wsgi.input"].read(
                    min(bytes_remaining, READ_CHUNK_SIZE)
                )
                if not chunk:
                    break
                bytes_remaining -= len(chunk)
                ofp.write(chunk)
                hash_sha256.update(chunk)
    except FileExistsError as exc:
        rv = HTTPResponse(status=HTTPStatus.CONFLICT, body=str(exc))
    except OSError as exc:
        if exc.errno == errno.ENOSPC:
            rv = HTTPResponse(
                status=HTTPStatus.INSUFFICIENT_STORAGE,
                body=f"Out of space on {context.meta[CTX_DIRECTORY]}",
            )
        else:
            rv = HTTPResponse(
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
                body=f"Unexpected error ({exc.errno}) encountered during file upload: {exc}",
            )
        remove_file = True
    except Exception as exc:
        rv = HTTPResponse(
            status=HTTPStatus.INTERNAL_SERVER_ERROR,
            body=f"Unexpected error encountered during file upload: {exc}",
        )
        remove_file = True
    else:
        if bytes_remaining:
            rv = HTTPResponse(
                status=HTTPStatus.BAD_REQUEST,
                body="Expected {} bytes but received {} bytes".format(
                    request.content_length, request.content_length - bytes_remaining
                ),
            )
            remove_file = True
        elif hash_sha256.hexdigest() != file_id:
            rv = HTTPResponse(
                status=HTTPStatus.BAD_REQUEST,
                body="Mismatched hash ID:  expecting {!r}, got {!r}".format(
                    file_id, hash_sha256.hexdigest()
                ),
            )
            remove_file = True
        else:
            rv = HTTPResponse(status=HTTPStatus.CREATED, body="Success")

    try:
        if remove_file:
            target.unlink(missing_ok=True)
    finally:
        if rv.status_code == HTTPStatus.CREATED:
            logging.info(
                'file id "%s" uploaded successfully, disk %s',
                file_id,
                get_disk_utilization_str(context.meta[CTX_DIRECTORY]),
            )
        else:
            logging.info(
                'file id "%s" upload failed:  %s, %s',
                file_id,
                rv.status_line,
                rv.body,
            )
        return rv


@app.delete("/<secret>/<file_id>")
@validate_secret
@click.pass_context
def delete_file(context: click.Context, file_id: str) -> HTTPResponse:
    """Deletes the local storage of the indicated file

    Args:
        context:  the Click context object
                    - for access to the local files directory path
        file_id:  the SHA256 hash of the file to be removed

    Returns:
        An HTTP response indicating the success of the file removal
    """
    logging.info('request to delete file id "%s"', file_id)
    target = context.meta[CTX_DIRECTORY] / file_id
    try:
        target.unlink()
    except FileNotFoundError as exc:
        return HTTPResponse(status=HTTPStatus.NOT_FOUND, body=str(exc))
    except PermissionError as exc:
        return HTTPResponse(status=HTTPStatus.FORBIDDEN, body=str(exc))
    except Exception as exc:
        return HTTPResponse(status=HTTPStatus.INTERNAL_SERVER_ERROR, body=str(exc))
    return HTTPResponse(status=HTTPStatus.OK, body="Success")


@click.command()
@click.option(
    "--secret",
    prompt=True,
    required=True,
    help='"secret" string (first part of URL; will prompt if unspecified)',
)
@click.option(
    "--bind",
    prompt=True,
    required=True,
    default=DEFAULT_ADDRESS + ":" + str(DEFAULT_PORT),
    show_default=True,
    help="Listen binding ([<name-or-IP>][:<port>]) (will prompt if unspecified)",
)
@click.option(
    "--files-directory",
    required=True,
    default=DEFAULT_FILES_DIRECTORY,
    show_default=True,
    help="Directory path for file storage (will prompt if unspecified)",
)
@click.option(
    "--debug",
    is_flag=True,
    required=False,
    default=False,
    help="Set Bottle's DEBUG mode",
)
@click.pass_context
def main(context, secret, bind, files_directory, debug) -> None:
    """The main function for the relay micro-server

    Using the Click support, we parse the command line, extract the
    configuration information, store some of it in the Click context, and start
    the Bottle server running.  The micro-server runs until a Ctrl-C is entered
    at the terminal or until a DELETE request is received on the server URI.
    """
    fd_path = Path(files_directory)
    if not fd_path.exists():
        context.fail(f"Files directory path {files_directory!r} does not exist.")
    elif not fd_path.is_dir():
        context.fail(f"Files directory path {files_directory!r} is not a directory.")

    port = DEFAULT_PORT
    if ":" in bind:
        host, port_str = bind.split(":", 1)
    else:
        host, port_str = bind, ""
    if not host:
        host = DEFAULT_ADDRESS
    if port_str:
        try:
            port = int(port_str)
        except ValueError:
            context.fail(f"Port value, {port_str!r}, must be an integer.")
    if not 0 < port <= 65536:
        context.fail(f"Port value, {port}, must be between 0 and 65536.")

    context.meta[CTX_DIRECTORY] = fd_path
    context.meta[CTX_SECRET] = secret

    try:
        app.run(host=host, port=port, debug=debug)
    except Exception as exc:
        context.fail(f"Error running the server:  {exc!s}")

    context.exit()
