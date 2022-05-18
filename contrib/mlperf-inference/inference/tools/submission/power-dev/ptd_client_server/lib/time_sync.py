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

from typing import Any, Callable
import datetime
import logging
import os
import subprocess
import sys
import time

from ptd_client_server.lib.external import ntplib  # type: ignore


CRITICAL_DIFFERENCE_TIME_MS = 200


def get_ntp_response(server: str) -> Any:
    ntp_client = ntplib.NTPClient()  # type: ignore
    return ntp_client.request(server, version=4)  # type: ignore


def validate_ntp(server: str) -> bool:
    response = get_ntp_response(server)
    offset_in_ms = response.offset * 1000
    logging.info(
        f"NTP:offset = {response.offset:.3f} s, delay = {response.delay:.3f} s "
    )
    is_ntp_synced = bool(abs(offset_in_ms) < CRITICAL_DIFFERENCE_TIME_MS)
    if not is_ntp_synced:
        logging.warning(
            f"The time offset between the system time and {server} is more then {CRITICAL_DIFFERENCE_TIME_MS} ms ({offset_in_ms:.3f} ms)"
        )
    return is_ntp_synced


def ntp_sync(server: str) -> bool:
    try:
        if not validate_ntp(server):
            set_ntp(server)
            return validate_ntp(server)
    except Exception:
        logging.exception(f"Could not synchronize with {server}")
        return False
    return True


def sync(
    server: str,
    get_remote_time: Callable[[], float],
    set_ntp_remote: Callable[[], str],
) -> bool:
    logging.info(f"Synchronizing with the server and with {server}...")
    try:
        if not validate_ntp(server) or not validate_remote(get_remote_time):
            set_ntp_remote()
            set_ntp(server)
            if not validate_ntp(server):
                logging.error(f"Could not synchronize with {server}")
                return False
            if not validate_remote(get_remote_time):
                logging.error("Could not synchronize with the server")
                return False
    except Exception:
        logging.exception("Got an exception. Could not synchronize")
        return False
    return True


def validate_remote(command: Callable[[], float]) -> bool:
    time1 = time.time()
    remote_time = command()
    time2 = time.time()
    dt1 = 1000 * (time1 - remote_time)
    dt2 = 1000 * (time2 - remote_time)
    logging.info(
        f"The time difference between the client and the server is within range {dt1:.3f} ms..{dt2:.3f} ms"
    )

    if max(abs(dt1), abs(dt2)) > CRITICAL_DIFFERENCE_TIME_MS:
        logging.warning(
            f"The time difference between the client and the server is more than {CRITICAL_DIFFERENCE_TIME_MS} ms"
        )
        return False
    return True


def set_ntp(server: str) -> None:
    logging.info(f"Synchronizing with {server} time using NTP...")

    if sys.platform == "win32":
        import win32api  # type: ignore

        try:
            response = get_ntp_response(server)
            synced_time = time.time() + response.offset
            utcTime = datetime.datetime.utcfromtimestamp(synced_time)
            win32api.SetSystemTime(
                utcTime.year,
                utcTime.month,
                utcTime.weekday(),
                utcTime.day,
                utcTime.hour,
                utcTime.minute,
                utcTime.second,
                int(utcTime.microsecond / 1000),
            )
        except Exception:
            logging.exception(
                "Could not set system time. You can synchronize time between client and server manually."
            )
            raise
    else:
        command = ["ntpdate", "-b", "--", server]
        if os.getuid() != 0:
            command = ["sudo", "-n"] + command

        try:
            subprocess.run(command, input="", check=True)
        except Exception:
            logging.error(
                "Could not set system time using ntpd. You can synchronize time between client and server manually."
            )
            raise
    # It could take sometime to set system time
    time.sleep(1)
    logging.info(f"Set system time at {str(datetime.datetime.now())}")
