def pbench_agent_config(tmpdir, config):
    """Create an agent configuration file given a config"""
    pbench_install_dir = tmpdir / "pbench-agent"
    pbench_install_dir.mkdir()

    pbench_config = pbench_install_dir / "pbench-agent.cfg"
    pbench_config.write(config)
    return pbench_config


def stub_agent_root_dir(tmpdir):
    """Create a root agent directory"""
    pbench_install_dir = tmpdir / "pbench-agent"
    pbench_install_dir.mkdir()
    return pbench_install_dir
