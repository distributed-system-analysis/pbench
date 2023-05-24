### End-to-End Workflow

Each command in pbench-agent accepts the `--help` option and outputs a brief usage message

The default set of tools for data collection can be enabled with

	$pbench-register-tool-set

To list all your registered tools

	$pbench-list-tools

You may then perform a built-in benchmark by running it's Pbench script

	$pbench-user-benchmark – sleep 10

The above command will collect data from the registered tools for the specified time period and save it in the `/var/lib/pbench-agent` directory.

To move the results, the outcomes are tarred and sent to the configured pbench-server with

	$pbench-results-move
