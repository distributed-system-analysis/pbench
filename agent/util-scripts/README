helper-scripts:

These scripts don't implement the benchmarks or tools, but support the setup &
execution of them.

register-tool: tell pbench you want to use this tool
list-tools: tell me what tools I have registered
clear-tools: clear all tools or filter by name or group
kill-tools: kill any running tools, should you abort a benchmark before it
            calls stop-tools
start-tools: tell pbench to start your registered tools (can be from
             cmdline or can be called from a benchmark script)
stop-tools: same as above, but stop
postprocess-tools: format the data collected from running the tools,
                   including d3.js graphs
avg-stddev: calculate average and standard deviation gievn a sample of inputs
            (used by benchmark scripts)
clear-results: delete all benchmark results that are in /var/lib/pbench
clear-tools: forget all registered tools
cleanup: clean up everything, including results and what tools have been
         registered
move-results: move result tar ball to archive results host
copy-results: same as above, but don't remove the local data
install-pub-key: installs a given ssh RSA key given my the administrator
                 allowing scp access to the results tar ball location
