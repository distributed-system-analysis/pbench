"""Common test support functions."""
import json

from filelock import FileLock
from pathlib import Path
from typing import Callable


def on_disk_config(
    tmp_path_factory, prefix: str, setup_func: Callable[[Path], Path]
) -> dict:
    """Base on-disk configuration recorder.  It returns a dictionary with two
    items, "tmp" and "cfg_dir", two Path objects for the temporary directory
    in which the configuration directory is created.

    The first argument is the temporary directory creator factory to be used.

    The second argument is a prefix to use for the JSON marker file in which
    will be store the dictionary containing the temporary directory and the
    configuration directory created by the setup_func.

    The third argument is the setup function itself.

    The setup_func is expected to take one argument, a Path object
    representing the created temporary directory, which this method invokes
    before it is called.
    """
    root_tmp_dir = tmp_path_factory.getbasetemp()
    marker = root_tmp_dir / f"{prefix}-marker.json"
    with FileLock(f"{marker}.lock"):
        if marker.is_file():
            the_setup = json.loads(marker.read_text())
            the_setup["tmp"] = Path(the_setup["tmp"])
            the_setup["cfg_dir"] = Path(the_setup["cfg_dir"])
        else:
            tmp_d = tmp_path_factory.mktemp(f"{prefix}-tmp")
            cfg_dir = setup_func(tmp_d)
            marker.write_text(json.dumps(dict(tmp=str(tmp_d), cfg_dir=str(cfg_dir))))
            the_setup = dict(tmp=tmp_d, cfg_dir=cfg_dir)
    return the_setup
