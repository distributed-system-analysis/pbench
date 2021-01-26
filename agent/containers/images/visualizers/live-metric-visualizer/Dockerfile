# To be ran from parent 'visualize' directory: podman build -t <name> -f live-metric-visualizer/Dockerfile .
FROM fedora:latest

WORKDIR = /

ENV GRAFANA_VERSION=7.3.6-1

RUN yum install -y wget pip && \
    pip3 install requests && \
    yum -y clean all && rm -rf /var/cache/yum/* && rm -rf ~/.cache/pip/* && \
    dnf -y install https://dl.grafana.com/oss/release/grafana-${GRAFANA_VERSION}.x86_64.rpm && \
    yum -y install grafana-pcp
    
ADD grafana_setup.py .
ADD nodefull.json .
ADD dcgm.json .
ADD combo.json .

## THE FOLLOWING LINE WAS PARTIALLY TAKEN FROM https://github.com/grafana/grafana-docker/blob/master/Dockerfile#L7#L13
ENV PATH=/usr/share/grafana/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    GF_DEFAULT_APP_MODE="development" \
    GF_PATHS_CONFIG="/etc/grafana/grafana.ini" \
    GF_PATHS_DATA="/var/lib/grafana" \
    GF_PATHS_HOME="/usr/share/grafana" \
    GF_PATHS_LOGS="/var/log/grafana" \
    GF_PATHS_PLUGINS="/var/lib/grafana/plugins" \
    GF_PATHS_PROVISIONING="/etc/grafana/provisioning"

EXPOSE 3000

COPY run.sh .
ENV VIS_TYPE="live"
ENV COLLECTOR=":"

RUN chmod +x run.sh

CMD ["./run.sh"]
