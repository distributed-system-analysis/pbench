# LiveMetricVisualizer
- Build locally with podman build -t <name> -f DockerfileLive .
- Available at quay.io/pbench/live-metric-visualizer
- A tool available to visualize Prometheus and PCP data live during a Pbench benchmark run

- Directions:
  -   `podman pull pbench/live-metric-visualizer`
  -   `podman run --network host pbench/live-metric-visualizer`

- NOTES:
  - Only the grafana server with preconfigured data sources for prometheus and PCP, as well as preloaded dashboards
  - Will work for live metric viewing (as pbench launches prometheus and pmlogger/pmproxy), but not for post-run visualization
  - Default Grafana credentials are: admin/admin


# PromGrafContainer
- Build locally with podman build -t <name> -f DockerfilePostProm .
- Available at quay.io/pbench/prom-graf-visualizer
- A tool available to visualize Prometheus data collected through Pbench after a benchmark run
- Preloaded dashboards for node-exporter and grafana

- Directions:
  -   `podman pull pbench/prom-graf-visualizer`
  -   `podman run -p 3000:3000 -p 9090:9090 -v absolute/path/to/prometheus_data:/data:Z -v absolute/path/to/prometheus.yml:/prometheus.yml:Z pbench/prom-graf-visualizer`

- NOTES: 
  - Both prometheus data (from tarball in tools-default/prometheus) and prometheus.yml (in tm dir) are available within pbench results.
  - Default Grafana credentials are: admin/admin
