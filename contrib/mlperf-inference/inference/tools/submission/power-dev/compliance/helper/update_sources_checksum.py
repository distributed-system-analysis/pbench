#!/usr/bin/env python3
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

import os
import json
import sys

compliance_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
project_dir = os.path.dirname(compliance_dir)
ptd_client_server_dir = os.path.join(project_dir, "ptd_client_server")

sys.path.append(ptd_client_server_dir)

from lib import source_hashes  # type: ignore # noqa


def update_sources_checksum() -> None:
    calc_s = source_hashes.get_sources_checksum(ptd_client_server_dir)
    sources_checksums_path = os.path.join(compliance_dir, "sources_checksums.json")

    with open(sources_checksums_path) as f:
        sources_sample = json.load(f)

    if calc_s in sources_sample:
        print(f"{sources_checksums_path!r} up to date")
        return

    sources_sample.append(calc_s)

    with open(sources_checksums_path, "w", encoding="utf-8") as f:
        json.dump(sources_sample, f, ensure_ascii=False, indent=4)

    print(f"{sources_checksums_path!r} has been updated")


if __name__ == "__main__":
    update_sources_checksum()
