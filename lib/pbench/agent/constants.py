"""Constants for the Pbench Agent.
"""

# Default Redis server port number used is "One Tool" in hex 0x17001
def_redis_port = 17001

# Default port number used for the Tool Data Sink
def_wsgi_port = 8080

# The amount of time a TM tries to publish its setup message.
TDS_RETRY_PERIOD_SECS = 60

# Prefix name for all channels used by Tool Meisters and the Tool Data Sink.
cli_tm_channel_prefix = "pbench-agent-cli"

# Channel suffixes to and from the client with the Tool Data Sink
tm_channel_suffix_to_client = "to-client"
tm_channel_suffix_from_client = "from-client"
# Channel suffixes to and from the Tool Meisters with the Tool Data Sink
tm_channel_suffix_to_tms = "to-tms"
tm_channel_suffix_from_tms = "from-tms"
# Channel suffix for the Tool Meister logging channel
tm_channel_suffix_to_logging = "to-logging"
# Tool-Meisters info key
tm_data_key = "tool-meister-data-key"

# List of allowed actions from the Pbench Agent CLI commands.
cli_tm_allowed_actions = frozenset(("start", "stop", "send"))

# List of API allowed actions
api_tm_allowed_actions = cli_tm_allowed_actions | frozenset(("end", "init", "sysinfo"))

# List of all allowed actions
tm_allowed_actions = api_tm_allowed_actions | frozenset(("terminate",))

# The list of convenience names for specifying sysinfo behaviors.
sysinfo_opts_convenience = frozenset(("all", "default", "none"))

# The default set of system configuration information collected.
sysinfo_opts_default = frozenset(
    ("block", "kernel_config", "libvirt", "security_mitigations", "sos", "topology")
)
# All of the available system configuration items that could be collected.
sysinfo_opts_available = sysinfo_opts_default | frozenset(("ara", "insights"))
