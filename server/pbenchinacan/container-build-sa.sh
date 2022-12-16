#!/usr/bin/env bash
#
# This script builds a stand-alone Pbench Server container with just the base
# software installed.
#

set -o errexit

#+
# Configuration definition section.
#-

BASE_IMAGE=${BASE_IMAGE:-registry.access.redhat.com/ubi9:latest}
RPM_PATH=${RPM_PATH:-/root/sandbox/rpmbuild/RPMS/noarch/pbench-server-*.rpm}

# Locations on the host
GITTOP=${GITTOP:-$(git rev-parse --show-toplevel)}

PBINC_SERVER=${GITTOP}/server
# Image tag determined from jenkins/branch.name
PB_SERVER_IMAGE_TAG=${PB_SERVER_IMAGE_TAG:-$(< ${GITTOP}/jenkins/branch.name)}

# Locations inside the container
INSTALL_ROOT=/opt/pbench-server
SERVER_LIB=${INSTALL_ROOT}/lib
CONF_PATH=${SERVER_LIB}/config/pbench-server.cfg

#+
# Configuration verification section.
#-

if (( $(ls ${RPM_PATH} 2>/dev/null | wc -l) != 1 ))
then
    echo "RPM_PATH (${RPM_PATH}) does not uniquely identify the RPM file" >&2
    exit 2
fi

#+
# Container build section.
#-

# Open a copy of the base container.  Docker format is required in order to set
# the hostname.
container=$(buildah from --format=docker ${BASE_IMAGE})

# Provide a few useful defaults for labels and the host name to use, and expose
# port 8080 for the Nginx proxy server.
buildah config \
    --label maintainer="Pbench Maintainers <pbench@googlegroups.com>" \
    --port 8080      `# pbench-server` \
    $container

buildah copy $container ${RPM_PATH} /tmp/pbench-server.rpm
buildah run $container dnf update -y
buildah run $container dnf install -y --setopt=tsflags=nodocs \
        https://dl.fedoraproject.org/pub/epel/epel-release-latest-9.noarch.rpm
buildah run $container dnf install -y /tmp/pbench-server.rpm nginx less rsyslog rsyslog-mmjsonparse
buildah run $container dnf clean all
buildah run $container rm -f /tmp/pbench-server.rpm

# Work around a problem with cron running jobs as other users in a container.
buildah run $container bash -c "sed -i -e '/pam_loginuid/ s/^/#/' /etc/pam.d/crond"
# Keep cron from complaining about inability to connect to systemd-logind
buildah run $container bash -c "sed -i -e '/pam_systemd/ s/^/#/' /etc/pam.d/system-auth"

# Add our Pbench Server Nginx configuration.
buildah copy --chown root:root --chmod 0644 $container \
    ${PBINC_SERVER}/lib/config/nginx.conf /etc/nginx/nginx.conf

# Since we configure Nginx to log via syslog directly, remove Nginx log rotation
# configuration as it emits unnecessary "Permission denied" errors.
buildah run $container rm /etc/logrotate.d/nginx

# Setup the Pbench Server systemd service.
buildah run $container cp ${SERVER_LIB}/systemd/pbench-server.service \
    /etc/systemd/system/pbench-server.service

buildah run $container systemctl enable nginx
buildah run $container systemctl enable rsyslog
buildah run $container systemctl enable pbench-server

# Create the container image.
buildah commit $container localhost/pbench-server:${PB_SERVER_IMAGE_TAG}
