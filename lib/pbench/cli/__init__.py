from typing import Any, Callable, List

import click


class CliContext:
    """Pbench CLI Click context object

    Create a click context object that holds the state of the command
    invocation. The CliContext will keep track of passed parameters,
    what command created it, which resources need to be cleaned up,
    and etc.

    We create an empty object at the beginning and populate the object
    with configuration, group names, at the beginning of the agent
    execution.
    """

    pass


pass_cli_context = click.make_pass_decorator(CliContext, ensure=True)


def options_callback(ctx: click.Context, _param, value: Any) -> Any:
    """Click option callback which captures the option in the context"""
    clictx = ctx.ensure_object(CliContext)
    clictx.config = value
    return value


def compose_options(cmd_func: Callable, opt_list: List[Callable]) -> Callable:
    """Utility function which composes a list of click.options into a single decorator

    Args:
        cmd_func:  the Click command function to be decorated
        opt_list:  a list of click.option invocations to compose

    Returns:
        A composite decorator function value
    """
    if not opt_list:
        return cmd_func
    else:
        opt_func = opt_list.pop()
        return opt_func(compose_options(cmd_func, opt_list))
