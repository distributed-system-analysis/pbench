import subprocess


def capture(command):
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,)
    out, err = proc.communicate()
    return out, err, proc.returncode


def test_pbench_config():
    command = ["pbench-config"]
    out, err, exitcode = capture(command)
    assert exitcode == 1


def test_pbench_config_help():
    command = ["pbench-config", "--help"]
    out, err, exitcode = capture(command)
    assert b"--help" in out
    assert exitcode == 0


def test_pbench_agent_config(monkeypatch, tmpdir):
    cfg = tmpdir / "pbench-agent.cfg"
    pbench_config = """
    [pbench-agent]
    pbench_run = /tmp
    """
    cfg.write(pbench_config)
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(cfg))
    command = ["pbench-config", "pbench_run", "pbench-agent"]
    out, err, exitcode = capture(command)
    assert b"/tmp" in out
    assert exitcode == 0


def test_pbench_server_config(monkeypatch, tmpdir):
    cfg = tmpdir / "pbench-server.cfg"
    pbench_config = """
    [pbench-server]
    pbench_tmp_dir = /tmp
    """
    cfg.write(pbench_config)
    monkeypatch.setenv("_PBENCH_SERVER_CONFIG", str(cfg))
    command = ["pbench-config", "pbench_tmp_dir", "pbench-server"]
    out, _, exitcode = capture(command)
    assert b"/tmp" in out
    assert exitcode == 0
