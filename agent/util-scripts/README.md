`agent/util-scripts`:

These scripts don't implement the benchmarks or tools, but support the setup & execution of them.

 * `register-tool`: register a tool to be started/stopped on one or more hosts
 * `register-tool-set`: register a set of tools to be started/stopped on one or more hosts
 * `list-tools`: display the list of tools registered on various hosts
 * `clear-tools`: clear all registered tools on all hosts, or those filtered by name or host

 * `tool-meister-start`: TBD
 * `start-tools`: start the registered tools (can be from cmdline or can be called from a benchmark script)
 * `stop-tools`: same as above, but stop
 * `send-tools`: TBD
 * `postprocess-tools`: format the data collected from running the tools, including D3 graphs
 * `tool-meister-stop`: TBD

 * `log-timestamp`: TBD
 * `avg-stddev`: calculate average and standard deviation of a given a sample of inputs (used by benchmark scripts)

 * `clear-results`: delete all benchmark results that are in `/var/lib/pbench-agent`
 * `move-results`: move result tar ball to archive results host
 * `copy-results`: same as above, but don't remove the local data
