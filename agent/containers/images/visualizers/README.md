# LiveMetricVisualizer
- A tool available to visualize Prometheus and PCP data live during a Pbench benchmark run

- Build locally with `podman build -t <name> -f DockerfileLive .`
- Available at quay.io/pbench/live-metric-visualizer

- Directions:
  -   `podman pull pbench/live-metric-visualizer`
  -   `podman run --network host pbench/live-metric-visualizer`
  -   To visualize a run on a remote host, add `-e HOST=<host>`
    - If prometheus is on a different host, it can be individually set with `-e PROM_HOST=<host>`
    - If pmproxy is on a different host, it can be individually set with `-e PM_HOST=<host>`
  -   To change to a custom prometheus port, add `-e PROM_PORT=<port>`
  -   To change to a custom pmproxy port, add `-e PM_PORT=<port>`

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
  -   `podman run -p 3000:3000 -p 9090:9090 -v absolute/path/to/prometheus_data:/data:Z  pbench/prom-graf-visualizer`

- NOTES: 
  - Prometheus data (from prometheus tarball in tools-default) is available within pbench results.
  - Default Grafana credentials are: admin/admin

# PCPGrafVisualizer
- A tool available to visualize PCP data collected through Pbench after a benchmark run

- Build locally with `podman build -t <name> -f DockerfilePostPCP .`
- Available at quay.io/pbench/pcp-graf-visualizer
- Preloaded dashboards for pcp data visualization

- Directions:
  -   `podman pull pbench/pcp-graf-visualizer`
  -   `podman run --network host -v /<path>/<to>/<pcp_log_folder>/data:/var/log/pcp/pmlogger:Z  pbench/pcp-graf-visualizer`
  - If you would rather use your own existing redis instance rather than have one launch internally:
    - You must specify redis host with `-e REDIS_HOST=<port>`
    - If not on the default port (6379), you can also add `-e REDIS_PORT=<port>`

- NOTES:
  - PCP data (from pcp data tarball in tools-default) is available within pbench results.
  - Default Grafana credentials are: admin/admin
