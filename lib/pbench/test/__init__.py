"""Common test support functions."""
import json

from filelock import FileLock
from pathlib import Path
from typing import Callable


def on_disk_config(
    tmp_path_factory, prefix: str, setup_func: Callable[[Path], Path]
) -> dict[Path, Path]:
    """Base on-disk configuration recorder.

    Callers use this method to ensure an on-disk configuration is only created
    once for a given prefix.

    Args:
        tmp_path_factory:  the temporary directory creator factory to be used
        prefix:            a value to be prefixed to the name of the JSON marker
                           file in which will be store the dictionary containing
                           the temporary directory and the configuration
                           directory created by the setup_func.
        setup_func:        the setup function provided by the caller, which
                           expects to be called with a Path argument for the
                           temporary directory to use, and returns a Path object
                           for the configuration directory created.

    Returns:
        a dictionary with two items, "tmp" and "cfg_dir", two Path objects for
        the temporary directory in which the configuration directory is created
    """
    root_tmp_dir = tmp_path_factory.getbasetemp()
    marker = root_tmp_dir / f"{prefix}-marker.json"
    with FileLock(f"{marker}.lock"):
        if marker.exists():
            the_setup = json.loads(marker.read_text())
            the_setup["tmp"] = Path(the_setup["tmp"])
            the_setup["cfg_dir"] = Path(the_setup["cfg_dir"])
        else:
            tmp_d = tmp_path_factory.mktemp(f"{prefix}-tmp")
            cfg_dir = setup_func(tmp_d)
            marker.write_text(json.dumps(dict(tmp=str(tmp_d), cfg_dir=str(cfg_dir))))
            the_setup = dict(tmp=tmp_d, cfg_dir=cfg_dir)
    return the_setup
