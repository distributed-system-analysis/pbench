#!/bin/bash
# base-tool generated command file

LANG=C PYTHONUNBUFFERED=True GOPATH=/var/tmp/pbench-test-tool-scripts/go PATH=${PATH}:${GOPATH}/bin exec /var/tmp/pbench-test-tool-scripts/opt/pbench-agent/tool-scripts/datalog/prometheus-metrics-datalog /var/tmp/pbench-test-tool-scripts/prometheus-metrics/tools-group/prometheus-metrics 42 tests/prometheus-metrics/inventory-hosts.lis
