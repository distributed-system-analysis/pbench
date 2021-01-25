# PromGrafContainer

- Available at quay.io/pbench/prom-graf-visualizer
- A tool available to visualize Prometheus data collected through Pbench after a benchmark run
- Preloaded dashboards for node-exporter and grafana

- Directions:
  -   `podman pull pbench/prom-graf-visualizer`
  -   `podman run -p 3000:3000 -p 9090:9090 -v absolute/path/to/prometheus_data:/data:Z -v absolute/path/to/prometheus.yml:/prometheus.yml:Z pbench/prom-graf-visualizer`

- NOTES: 
  - Both prometheus data (from tarball in tools-default/prometheus) and prometheus.yml (in tm dir) are available within pbench results.
  - Default Grafana credentials are: admin/admin
