# Copyright 2018 The MLPerf Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =============================================================================

from collections import OrderedDict
from typing import Any, Dict, List
import hashlib
import inspect
import logging
import os
import pathlib
import sys

_source_hashes: object = None

_module_name = "ptd_client_server.lib"


def get() -> object:
    """Should be called after init()."""

    assert (
        _source_hashes is not None
    ), "_source_hashes is None. init() should be called first"
    return _source_hashes


def init() -> None:
    """Populate the global variable containing source code checksums.
    Should be called right after importing all modules.
    Note that source files could change mid-execution, so this should be called
    as early as possible.
    """

    global _source_hashes

    assert _source_hashes is None, "init() already called"

    base_dir = pathlib.Path(__file__).parent.parent

    result: Any = {
        "sources": {},
        "modules": {},
    }

    result["sources"] = get_sources_checksum(base_dir)

    for name, module in sys.modules.items():
        if not (name == _module_name or name.startswith(_module_name + ".")):
            continue

        try:
            source = inspect.getsource(sys.modules[name])
            fname_ = inspect.getsourcefile(sys.modules[name])
            assert fname_ is not None
            fname = fname_
        except (TypeError, OSError):
            # TypeError: <module 'sys' (built-in)> is a built-in module
            # OSError: source code not available
            continue

        hash = hashlib.sha1(source.encode("utf8")).hexdigest()
        relpath = _normalize(os.path.relpath(fname, base_dir))

        if relpath not in result["sources"]:
            logging.fatal(
                f"Module {name} at {relpath!r} is not within the source code directory"
            )
            exit(1)
        if result["sources"][relpath] != hash:
            logging.fatal(
                f"Module {name} at {relpath!r} hash mismach {result['sources'][relpath]} != {hash}"
            )
            exit(1)

        result["modules"][name] = relpath

    result["sources"] = _sort_dict(result["sources"])
    result["modules"] = _sort_dict(result["modules"])

    _source_hashes = result


def get_sources_checksum(base_dir: pathlib.Path) -> Dict[str, str]:
    result = {}

    for path, dirs, files in os.walk(base_dir, topdown=True):
        exclude = {
            "__pycache__",
            ".mypy_cache",
            ".pytest_cache",
        }
        dirs[:] = [d for d in dirs if d not in exclude]

        relpath = os.path.relpath(path, base_dir)
        if relpath == ".":
            relpath = ""
        for file in filter(lambda f: f.endswith(".py"), files):
            fname = os.path.join(relpath, file)
            with open(os.path.join(path, file), "rb") as f:
                b_source = f.read()
                if b"\r" in b_source:
                    logging.fatal(
                        f"{file} contains '\\r'."
                        "Make sure that source files are not converted to CRLF format."
                    )
                    exit(1)
                result[_normalize(fname)] = hashlib.sha1(b_source).hexdigest()

    return result


def _normalize(path: str) -> str:
    allparts: List[str] = []
    while 1:
        parts = os.path.split(path)
        if parts[0] == path:  # sentinel for absolute paths
            allparts.insert(0, parts[0])
            break
        elif parts[1] == path:  # sentinel for relative paths
            allparts.insert(0, parts[1])
            break
        else:
            path = parts[0]
            allparts.insert(0, parts[1])
    return "/".join(allparts)


def _sort_dict(x: Dict[str, Any]) -> "OrderedDict[str, Any]":
    return OrderedDict(sorted(x.items()))


def hash_dir(dirname: str) -> Dict[str, str]:
    result: Dict[str, str] = {}

    for path, dirs, files in os.walk(dirname, topdown=True):
        relpath = os.path.relpath(path, dirname)
        if relpath == ".":
            relpath = ""
        for file in files:
            fname = os.path.join(relpath, file)
            with open(os.path.join(path, file), "rb") as f:
                result[_normalize(fname)] = hashlib.sha1(f.read()).hexdigest()

    return _sort_dict(result)
