#!/bin/bash -e
#
# This script builds a container which, when run, starts a Pbench Server.
#

#+
# Configuration definition section.
#-
GITTOP=${GITTOP:-$(git rev-parse --show-toplevel)}

BASE_IMAGE=${BASE_IMAGE:-registry.access.redhat.com/ubi9:latest}
PB_SERVER_IMAGE_NAME=${PB_SERVER_IMAGE_NAME:-"pbench-server"}
PB_SERVER_IMAGE_TAG=${PB_SERVER_IMAGE_TAG:-$(< ${GITTOP}/jenkins/branch.name)}
RPM_PATH=${RPM_PATH:-/root/sandbox/rpmbuild/RPMS/noarch/pbench-server-*.rpm}
KEYCLOAK_CLIENT_SECRET=${KEYCLOAK_CLIENT_SECRET:-"client-secret"}

# Default target registry to use.
PB_CONTAINER_REG=${PB_CONTAINER_REG:-$(<${HOME}/.config/pbench/ci_registry.name)}

# Locations on the host
PBINC_SERVER=${GITTOP}/server
PBINC_INACAN=${PBINC_SERVER}/pbenchinacan

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

# Open a copy of the base container.
container=$(buildah from ${BASE_IMAGE})

buildah config \
    --entrypoint /sbin/init \
    --label maintainer="Pbench Maintainers <pbench@googlegroups.com>" \
    $container

buildah copy $container ${RPM_PATH} /tmp/pbench-server.rpm
buildah run $container dnf update -y
if [[ "${BASE_IMAGE}" == *"ubi9:latest" || "${BASE_IMAGE}" == *"centos:stream9" ]]; then
    buildah run $container dnf install -y --nodocs \
        https://dl.fedoraproject.org/pub/epel/epel-release-latest-9.noarch.rpm
fi
buildah run $container dnf install -y --nodocs \
    /tmp/pbench-server.rpm nginx less rsyslog rsyslog-mmjsonparse
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
buildah commit $container ${PB_CONTAINER_REG}/${PB_SERVER_IMAGE_NAME}:${PB_SERVER_IMAGE_TAG}
