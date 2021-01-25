FROM fedora:latest

WORKDIR /

ENV PROM_VERSION=2.18.1 \
    GRAFANA_VERSION=7.3.6-1

RUN yum install -y wget pip && \
    pip3 install requests && \
    wget -P /opt/ https://github.com/prometheus/prometheus/releases/download/v${PROM_VERSION}/prometheus-${PROM_VERSION}.linux-amd64.tar.gz && \
    tar xf /opt/prometheus-${PROM_VERSION}.linux-amd64.tar.gz && \
    rm -f /prometheus-${PROM_VERSION}.linux-amd64/prometheus.yml && \
    yum -y clean all && rm -rf /var/cache/yum/* && rm -rf ~/.cache/pip/* && \
    dnf -y install https://dl.grafana.com/oss/release/grafana-${GRAFANA_VERSION}.x86_64.rpm && \
    mkdir data
    
ADD prometheus.yml .
ADD prom_ds.py .
ADD nodefull.json .
ADD dcgm.json .
ADD combo.json .

## THE FOLLOWING LINE WAS TAKEN FROM https://github.com/grafana/grafana-docker/blob/master/Dockerfile#L7#L13
ENV PATH=/usr/share/grafana/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    GF_PATHS_CONFIG="/etc/grafana/grafana.ini" \
    GF_PATHS_DATA="/var/lib/grafana" \
    GF_PATHS_HOME="/usr/share/grafana" \
    GF_PATHS_LOGS="/var/log/grafana" \
    GF_PATHS_PLUGINS="/var/lib/grafana/plugins" \
    GF_PATHS_PROVISIONING="/etc/grafana/provisioning"

EXPOSE 3000
EXPOSE 9090

COPY run.sh .

RUN chmod +x run.sh

CMD ["./run.sh"]
