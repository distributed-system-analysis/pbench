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

from pathlib import Path
import pytest
import socket

from ptd_client_server.lib import server


def test_parse_listen() -> None:
    with pytest.raises(ValueError):
        server.get_host_port_from_listen_string("badaddress 1234")

    with pytest.raises(ValueError):
        server.get_host_port_from_listen_string("127.0.0.1")

    assert server.get_host_port_from_listen_string("127.0.0.1 1234") == (
        "127.0.0.1",
        1234,
    )

    assert server.get_host_port_from_listen_string("2001:db8::8a2e:370:7334 1234") == (
        "2001:db8::8a2e:370:7334",
        1234,
    )


def test_tcp_port_is_occupied() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", 9998))
        s.listen(10)

        assert server.tcp_port_is_occupied(9997) is False
        assert server.tcp_port_is_occupied(9998) is True
        assert server.tcp_port_is_occupied(9999) is False


def test_max_volts_amps(tmp_path: Path) -> None:
    with open(tmp_path / "logs_tmp", "wb") as f:
        f.write(
            b"Time,11-07-2020 17:49:06.145,NOTICE,Analyzer identity response of 32 bytes: YOKOGAWA,WT310,C2PH13047V,F1.03\n"
            b"Time,11-07-2020 17:54:49.071,ERROR,Bad volts reading nan from WT310\n"
            b"Buffer was 1.000E+00;1;300.0E+00;1\n"
            b"Time,01-22-2021 15:05:14.313,Watts,22.970000,Volts,227.370000,Amps,0.204340,PF,0.494400,Mark,2021-01-22_15-05-02_loadgen_ranging\n"
            b"Time,01-22-2021 15:05:15.322,Watts,25.650000,Volts,227.370000,Amps,0.225410,PF,0.500600,Mark,2021-01-22_15-05-02_loadgen_ranging\n"
            b"Time,01-22-2021 15:05:15.322,Watts,25.650000,Volts,227.370000,Amps,0.225410,PF,0.500600,Mark,2021-01-22_15-05-02_loadgen_ranging\n"
            b"Time,01-22-2021 15:05:15.322,Watts,25.650000,Volts,227.370000,Amps,0.225410,PF,0.500600,Mark,2021-01-22_15-05-02_loadgen_ranging\n"
            b"Time,11-13-2020 22:38:59.240,Watts,272.930000,Volts,-1.000000,Amps,-1.000000,PF,-1.000000,Mark,notset,Ch1,Watts,91.060000,Volts,120.950000,Amps,0.832100,PF,0.938900,Ch2,Watts,90.970000,Volts,120.830000,Amps,0.802000,PF,0.938800,Ch3,Watts,90.900000,Volts,120.750000,Amps,0.802000,PF,0.938700\n"
            b"Time,11-13-2020 22:39:00.239,Watts,275.630000,Volts,-1.000000,Amps,-1.000000,PF,-1.000000,Mark,notset,Ch1,Watts,91.960000,Volts,120.910000,Amps,0.810300,PF,0.938600,Ch2,Watts,91.870000,Volts,120.850000,Amps,0.810200,PF,0.938500,Ch3,Watts,91.800000,Volts,120.740000,Amps,0.810300,PF,0.938400\n"
            b"Time,11-13-2020 22:39:00.239,Watts,275.630000,Volts,-1.000000,Amps,-1.000000,PF,-1.000000,Mark,notset,Ch1,Watts,91.960000,Volts,120.910000,Amps,0.810300,PF,0.938600,Ch2,Watts,91.870000,Volts,120.830000,Amps,0.810400,PF,0.938500,Ch3,Watts,91.800000,Volts,120.730000,Amps,0.810200,PF,0.938400\n"
            b"Time,11-13-2020 22:39:00.239,Watts,275.630000,Volts,-1.000000,Amps,-1.000000,PF,-1.000000,Mark,notset1,Ch1,Watts1,91.960000,Volts,120.910000,Amps,0.810300,PF,0.938600,Ch2,Watts,91.870000,Volts,120.830000,Amps,0.810400,PF,0.938500,Ch3,Watts,91.800000,Volts,120.730000,Amps,0.810200,PF,0.938400\n"
        )

    assert server.max_volts_amps(str(tmp_path / "logs_tmp"), "notset", 3, 1) == (
        "120.750000",
        "0.810300",
    )
    assert server.max_volts_amps(str(tmp_path / "logs_tmp"), "notset", 2, 2) == (
        "120.850000",
        "0.810400",
    )
    with pytest.raises(server.ExtraChannelError) as excinfo:
        server.max_volts_amps(str(tmp_path / "logs_tmp"), "notset", 2, 4)
    assert "There are extra ptd channels in configuration" in str(excinfo.value)

    assert server.max_volts_amps(str(tmp_path / "logs_tmp"), "notset", 1, 3) == (
        "120.950000",
        "0.832100",
    )
    assert server.max_volts_amps(
        str(tmp_path / "logs_tmp"), "2021-01-22_15-05-02_loadgen_ranging", 0, 0
    ) == ("227.370000", "0.225410")

    assert server.max_volts_amps(
        str(tmp_path / "logs_tmp"), "2021-01-22_15-05-02_loadgen_ranging", 1, 0
    ) == ("227.370000", "0.225410")

    with pytest.raises(server.LitNotFoundError) as excinfo:
        server.max_volts_amps(str(tmp_path / "logs_tmp"), "notset1", 1, 3)
    assert "Expected 'Watts', got 'Watts1'" in str(excinfo.value)
