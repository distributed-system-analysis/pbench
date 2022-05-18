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

from typing import Any, List, Optional, Dict, Tuple
import dataclasses
import json
import time
import uuid

from ptd_client_server.lib import source_hashes


class _JsonEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if "to_json" in dir(o):
            return o.to_json()
        if isinstance(o, uuid.UUID):
            return str(o)
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return super().default(o)


class Summary:
    def __init__(self) -> None:
        self.session_name: Optional[str] = None
        self.client_uuid: Optional[uuid.UUID] = None
        self.server_uuid: Optional[uuid.UUID] = None
        self.timezone_offset = -time.localtime().tm_gmtoff
        self._messages: List[Any] = []
        self.ptd_messages: "Optional[PtdMessages]" = None
        self._results: Optional[Dict[str, str]] = None
        self._phases: Dict[str, List[Tuple[float, float]]] = {
            "ranging": [],
            "testing": [],
        }
        self.debug = False
        self.ptd_config: Optional[Dict[str, Any]] = None

        # TODO: move source_hashes into this module
        source_hashes_: Any = source_hashes.get()
        self._sources = source_hashes_["sources"]
        self._modules = source_hashes_["modules"]

    def message(
        self, cmd: Tuple[Optional[str], float], reply: Tuple[Optional[str], float]
    ) -> None:
        self._messages.append(
            {
                "cmd": cmd[0],
                "cmd_time": cmd[1],
                "reply": reply[0],
                "reply_time": reply[1],
            }
        )

    def phase(self, phase: str, n: int) -> None:
        assert phase in ("ranging", "testing")
        assert n in (0, 1, 2, 3)
        l = self._phases[phase]
        pair = time.time(), time.monotonic()
        if len(l) == n:
            l.append(pair)
        elif len(l) > n:
            l[n] = pair

    def hash_results(self, dirname: str) -> None:
        self._results = source_hashes.hash_dir(dirname)

    def save(self, fname: str) -> None:
        with open(fname, "w", newline="\n") as f:
            json.dump(self, f, cls=_JsonEncoder, indent=4)

    def to_json(self) -> Any:
        assert self.session_name is not None
        assert self.client_uuid is not None
        assert self.server_uuid is not None
        assert self._results is not None

        result: Any = {
            "version": "1.0",  # TODO: use global version?
            "timezone": self.timezone_offset,
            "modules": self._modules,
            "sources": self._sources,
            "messages": self._messages,
            "uuid": {"client": self.client_uuid, "server": self.server_uuid},
            "session_name": self.session_name,
            "results": self._results,
            "phases": self._phases,
        }
        if self.ptd_messages is not None:
            result["ptd_messages"] = self.ptd_messages
        if self.ptd_config:
            result["ptd_config"] = self.ptd_config
        if self.debug:
            result["debug"] = True
        return result


class PtdMessages:
    def __init__(self) -> None:
        self._m: Any = []

    def add(self, cmd: str, reply: str) -> None:
        self._m.append({"cmd": cmd, "reply": reply})

    def to_json(self) -> Any:
        return self._m
