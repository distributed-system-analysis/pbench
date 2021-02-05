"""
Starts by starting up grafana server, as well as any collectors (prometheus, pmproxy) if needed.

Then sets up all grafana plugins, data sources, and dashboards through grafana API.
Chooses what to upload/enable based off VIS_TYPE environment variable.

If VIS_TYPE is 'live' (default for live-metric-visualizer):
    - Node exporter/DCGM dashboards will be uploaded and enabled
    - Prometheus data source will be configured
    - Grafana-pcp plugin will be enabled
    - PCP redis and vector datasources will be configured
    - PCP default dashboards will be enabled
If VIS_TYPE is 'prom' (default for prom-graf-visualizer):
    - Node exporter/DCGM dashboards will be uploaded and enabled
    - Prometheus data source will be configured
If VIS_TYPE is 'pcp' (default for soon-to-come pcp-graf-visualizer):
    - Grafana-pcp plugin will be enabled
    - PCP redis and vector datasources will be configured
    - PCP default dashboards will be enabled
"""

import os
import json
import requests
import time
import subprocess

# Start the collector (if needed)
collector_cmd = os.environ["COLLECTOR"]
if not collector_cmd == "":
    collector = subprocess.Popen(collector_cmd.split(" "))
    if os.environ["VIS_TYPE"] == "pcp":
        subprocess.Popen("redis-server")
        for item in os.scandir(os.environ["PCP_ARCHIVE_DIR"]):
            if os.path.isdir(item):
                args = [
                    "pmseries",
                    "--load",
                    f"{os.environ['PCP_ARCHIVE_DIR']}/{item.name}",
                ]
                print(args)
                subprocess.Popen(args)
else:
    collector = None

# Start the grafana server
args = [
    "grafana-server",
    "-homepath",
    os.environ["GF_PATHS_HOME"],
    "-config",
    os.environ["GF_PATHS_CONFIG"],
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

metric_type = os.environ["VIS_TYPE"]
if metric_type == "live" or metric_type == "prom":
    prom_source_url = f"{graf_base}api/datasources"
    payload = {
        "name": "prometheus",
        "type": "prometheus",
        "url": "http://localhost:9090",
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
        "url": "http://localhost:44322",
        "access": "proxy",
        "basicAuth": False,
    }
    response = requests.post(pcp_source_url, headers=headers, json=payload)
    print(json.loads(response.content.decode("utf-8")))

    payload = {
        "name": "PCP Vector",
        "type": "pcp-vector-datasource",
        "url": "http://localhost:44322",
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
