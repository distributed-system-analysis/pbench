# LiveMetricVisualizer
- A tool available to visualize Prometheus and PCP data live during a Pbench benchmark run

- Build locally with `podman build -t <name> -f DockerfileLive .`
- Available at quay.io/pbench/live-metric-visualizer

- Directions:
  -   `podman pull pbench/live-metric-visualizer`
  -   `podman run --network host pbench/live-metric-visualizer`

- NOTES:
  - Container includes grafana server with preconfigured data sources and dashboards for both prometheus and PCP
  - Will work for live metric viewing (as pbench launches prometheus and pmlogger/pmproxy), but not for post-run visualization
  - Default Grafana credentials are: admin/admin


# PromGrafVisualizer
- A tool available to visualize Prometheus data collected through Pbench after a benchmark run

- Build locally with `podman build -t <name> -f DockerfilePostProm .`
- Available at quay.io/pbench/prom-graf-visualizer
- Preloaded dashboards for node-exporter and grafana

- Directions:
  -   `podman pull pbench/prom-graf-visualizer`
  -   `podman run -p 3000:3000 -p 9090:9090 -v absolute/path/to/prometheus_data:/data:Z -v absolute/path/to/prometheus.yml:/prometheus.yml:Z pbench/prom-graf-visualizer`

- NOTES: 
  - Both prometheus data (from tarball in tools-default/prometheus) and prometheus.yml (in tm dir) are available within pbench results.
  - Default Grafana credentials are: admin/admin

# PCPGrafVisualizer
- A tool available to visualize PCP data collected through Pbench after a benchmark run

- Build locally with `podman build -t <name> -f DockerfilePostPCP .`
- Available at quay.io/pbench/pcp-graf-visualizer
- Preloaded dashboards for pcp data visualization

- Directions:
  -   `podman pull pbench/pcp-graf-visualizer`
  -   `podman run -p 3000:3000 -p 44322:44322 -v /<path>/<to>/<pcp_log_folder>/data:/var/log/pcp/pmlogger:Z  pbench/pcp-graf-visualizer`

- NOTES:
  - PCP data (from pcp data tarball in tools-default) is available within pbench results.
  - Default Grafana credentials are: admin/admin
