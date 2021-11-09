"""
Starts by starting up grafana server, as well as any collectors (prometheus, pmproxy) if needed.

Then sets up all grafana plugins, data sources, and dashboards through grafana API.
Chooses what to upload/enable based off the visualizer type argument.

If the type is 'live' (default for live-metric-visualizer):
    - Node exporter/DCGM dashboards will be uploaded and enabled
    - Prometheus data source will be configured
    - Grafana-pcp plugin will be enabled
    - PCP redis and vector datasources will be configured
    - PCP default dashboards will be enabled
If the type is 'prom' (default for prom-graf-visualizer):
    - Node exporter/DCGM dashboards will be uploaded and enabled
    - Prometheus data source will be configured
If the type is 'pcp' (default for soon-to-come pcp-graf-visualizer):
    - Grafana-pcp plugin will be enabled
    - PCP redis and vector datasources will be configured
    - PCP default dashboards will be enabled
"""

import os
import sys
import json
import requests
import time
import subprocess

# Start the collector (if needed)
collector = None
metric_type = sys.argv[1]
if metric_type == "pcp":
    cmd = [
        "/usr/libexec/pcp/bin/pmproxy",
        "--foreground",
        "--timeseries",
        "--port=44566",
        "--redishost=localhost",
        "--redisport=6379",
        "--config=/etc/pcp/pmproxy/pmproxy.conf",
    ]
    redis_host = os.environ.get("REDIS_HOST", "NO_HOST")
    if not redis_host == "NO_HOST":
        cmd[4] = f"--redishost={redis_host}"
        redis_port = os.environ.get("REDIS_PORT", "NO_PORT")
        if not redis_port == "NO_PORT":
            cmd[5] = f"--redisport={redis_port}"
    else:
        subprocess.Popen("redis-server")
    collector = subprocess.Popen(cmd)
    log_path = "/var/log/pcp/pmlogger"
    for item in os.scandir(log_path):
        if os.path.isdir(item):
            rec_path = os.path.join(log_path, item.name)
            args = [
                "pmseries",
                "--load",
                rec_path,
            ]
            print(args)
            subprocess.Popen(args)
elif metric_type == "prom":
    cmd = [
        "./prometheus",
        "--config.file=/data/prometheus.yml",
        "--storage.tsdb.path=/data",
        "--storage.tsdb.retention.time=1y",
    ]
    collector = subprocess.Popen(cmd)

# Start the grafana server
os.environ["GF_DEFAULT_APP_MODE"] = os.environ.get("GF_DEFAULT_APP_MODE", "development")
os.environ["GF_PATHS_DATA"] = os.environ.get("GF_PATHS_DATA", "/var/lib/grafana")
os.environ["GF_PATHS_LOGS"] = os.environ.get("GF_PATHS_LOGS", "/var/log/grafana")
os.environ["GF_PATHS_PLUGINS"] = os.environ.get(
    "GF_PATHS_PLUGINS", "/var/lib/grafana/plugins"
)
os.environ["GF_PATHS_PROVISIONING"] = os.environ.get(
    "GF_PATHS_PROVISIONING", "/etc/grafana/provisioning"
)
args = [
    "grafana-server",
    "-homepath",
    os.environ.get("GF_PATHS_HOME", "/usr/share/grafana"),
    "-config",
    os.environ.get("GF_PATHS_CONFIG", "/etc/grafana/grafana.ini"),
    "$@",
    "cfg:default.log.mode=console",
]
grafana = subprocess.Popen(args)

graf_base = "http://localhost:3000/"

while True:
    try:
        response = requests.get(graf_base)
        if response.status_code == 200:
            break
    except Exception:
        time.sleep(0.1)

headers = {"Content-Type": "application/json", "Authorization": None}
payload = {"role": "Admin", "name": "new_api_key"}
response = requests.post(
    "http://admin:admin@localhost:3000/api/auth/keys", headers=headers, json=payload
)
token = json.loads(response.content.decode("utf-8"))["key"]
headers["Authorization"] = f"Bearer {token}"

if metric_type == "live":
    host = os.environ.get("HOST", "localhost")
    prom_host = os.environ.get("PROM_HOST", host)
    pm_host = os.environ.get("PM_HOST", host)
    prom_url = f"http://{prom_host}:"
    pm_url = f"http://{pm_host}:"
    prom_port = os.environ.get("PROM_PORT", "9090")
    pm_port = os.environ.get("PM_PORT", "44566")
else:
    prom_url = "http://localhost:"
    pm_url = prom_url
    prom_port = "9090"
    pm_port = "44566"

if metric_type == "live" or metric_type == "prom":
    prom_source_url = f"{graf_base}api/datasources"
    payload = {
        "name": "prometheus",
        "type": "prometheus",
        "url": prom_url + prom_port,
        "access": "proxy",
        "basicAuth": False,
    }
    response = requests.post(prom_source_url, headers=headers, json=payload)
    print(json.loads(response.content.decode("utf-8")))

    dashboard_url = f"{graf_base}api/dashboards/import"

    response = requests.post(
        dashboard_url, headers=headers, data=open("nodefull.json", "rb")
    )
    print(json.loads(response.content.decode("utf-8")))

    response = requests.post(
        dashboard_url, headers=headers, data=open("combo.json", "rb")
    )
    print(json.loads(response.content.decode("utf-8")))

    response = requests.post(
        dashboard_url, headers=headers, data=open("dcgm.json", "rb")
    )
    print(json.loads(response.content.decode("utf-8")), flush=True)

if metric_type == "live" or metric_type == "pcp":
    plugin_url = f"{graf_base}api/plugins/performancecopilot-pcp-app/settings"
    response = requests.post(
        plugin_url, headers=headers, json={"enabled": True, "pinned": True}
    )
    print(json.loads(response.content.decode("utf-8")))

    pcp_source_url = f"{graf_base}api/datasources"
    payload = {
        "name": "PCP Redis",
        "type": "pcp-redis-datasource",
        "url": pm_url + pm_port,
        "access": "proxy",
        "basicAuth": False,
    }
    response = requests.post(pcp_source_url, headers=headers, json=payload)
    print(json.loads(response.content.decode("utf-8")))

    payload = {
        "name": "PCP Vector",
        "type": "pcp-vector-datasource",
        "url": pm_url + pm_port,
        "access": "proxy",
        "basicAuth": False,
    }
    response = requests.post(pcp_source_url, headers=headers, json=payload)
    print(json.loads(response.content.decode("utf-8")), flush=True)

try:
    grafana.wait()
    if collector:
        collector.wait()
except KeyboardInterrupt:
    print("\nVisualizer closed!")
