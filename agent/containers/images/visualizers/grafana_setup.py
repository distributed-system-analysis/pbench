"""
Sets up all grafana plugins, data sources, and dashboards through grafana API
Includes PCP and prometheus options if run for live-metric-visualizer
Only prometheus options used for prom-graf-visualizer
Once PCP visualizer is made, will use only PCP options
"""

import os
import json
import requests
import subprocess
import time

graf_base = "http://localhost:3000/"

while True:
    try:
        response = requests.get(graf_base)
        if response.status_code == 200:
            break
    except Exception:
        time.sleep(0.1)

tokenholder = open("key.txt", "w")
args = [
    "curl",
    "http://localhost:3000/api/auth/keys",
    "-XPOST",
    "-uadmin:admin",
    "-H",
    "Content-Type: application/json",
    "-d",
    '{"role":"Admin","name":"new_api_key"}',
]
subprocess.run(args, stdout=tokenholder)
tokenholder.close()

tokenholder = open("key.txt", "r")
token_raw = tokenholder.readline()
tokenholder.close()
token_dict = json.loads(token_raw)
print(token_dict["key"])
token = token_dict["key"]

headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}

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
    print(json.loads(response.content.decode("utf-8")))

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
    print(json.loads(response.content.decode("utf-8")))
