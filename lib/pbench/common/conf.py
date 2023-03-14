from pbench.common import configtools


def common_main(prog: str, env: str):
    """Common entry point for agent and server pbench-config commands.

    Args:
        prog : invocation program name to use in Usage message
        env : environment variable for configuration file

    Returns:
        Pass through of return code from `configtools.main`
    """
    opts, args = configtools.parse_args(
        configtools.options,
        usage=f"Usage: {prog} [options] <item>|-a <section> [<section> ...]",
    )
    conf, files = configtools.init(opts, env)
    return configtools.main(conf, args, opts, files)
