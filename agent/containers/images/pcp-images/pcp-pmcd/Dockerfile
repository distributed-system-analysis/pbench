FROM fedora:33

ENV SUMMARY="Performance Co-Pilot" \
    DESCRIPTION="Performance Co-Pilot is a system performance analysis toolkit." \
    VERSION=5

RUN dnf install -y --setopt=tsflags=nodocs procps-ng gettext pcp pcp-zeroconf && \
    dnf install -y pcp-doc pcp-gui pcp-system-tools && \
    dnf clean all
RUN systemctl enable pmcd && systemctl disable pmlogger

COPY config /etc/sysconfig/pmcd

EXPOSE 44321
CMD ["/usr/sbin/init"]

