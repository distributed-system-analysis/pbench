#!/bin/bash

# Run collector (if needed), grafana setup, and grafana in parallel as grafana/collector are continuous processes
# and the grafana setup needs to be run while grafana is up
${COLLECTOR} &
python3 grafana_setup.py &
exec grafana-server                                         \
  --homepath="$GF_PATHS_HOME"                               \
  --config="$GF_PATHS_CONFIG"                               \
  "$@"                                                      \
  cfg:default.log.mode="console"                            \
  cfg:default.paths.data="$GF_PATHS_DATA"                   \
  cfg:default.paths.logs="$GF_PATHS_LOGS"                   \
  cfg:default.paths.plugins="$GF_PATHS_PLUGINS"             \
  cfg:default.paths.provisioning="$GF_PATHS_PROVISIONING"

## THE LINE ABOVE TO LAUNCH GRAFANA WAS TAKEN FROM https://github.com/grafana/grafana-docker/blob/master/run.sh#L74#L82
