# LiveMetricVisualizer

- Available at quay.io/pbench/live-metric-visualizer
- A tool available to visualize Prometheus and PCP data live during a Pbench benchmark run

- Directions:
  -   `podman pull pbench/live-metric-visualizer`
  -   `podman run --network host pbench/live-metric-visualizer`

- NOTE: 
  - Only the grafana server with preconfigured data sources for prometheus and PCP, as well as preloaded dashboards
  - Will work for live metric viewing (as pbench launches prometheus and pmlogger/pmproxy), but not for post-run visualization
  - Default Grafana credentials are: admin/admin
