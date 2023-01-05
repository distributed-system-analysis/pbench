#!/usr/bin/env bash
#
# This script builds a container which, when run, starts a Pbench Server.
#
# Note:  successfully running this script required adding CAP_SETFCAP (for the
#        installation of httpd) to the list of default capabilities in
#        /etc/containers/containers.conf (and, if that file doesn't exist,
#        you'll need to create it with the other default capabilities, e.g., see
#        https://man.archlinux.org/man/containers.conf.5.en#CONTAINERS_TABLE and
#        https://github.com/containers/common/blob/da56e470c0c57c27e91bdc844b32c5dab6611394/pkg/config/containers.conf#L48)
#

set -o errexit

# First we create the stand-alone Pbench Server container image.
. $(dirname ${0})/container-build-sa.sh

HOSTNAME_F=pbenchinacan

# Locations on the host
PBINC_DIR=${PBINC_SERVER}/pbenchinacan

# Open a copy of the base pbench server container.  Docker format is required
# in order to set the hostname.
container=$(buildah from --format=docker pbench-server:${PB_SERVER_IMAGE_TAG})

buildah config \
    --label maintainer="Pbench Maintainers <pbench@googlegroups.com>" \
    --hostname $HOSTNAME_F \
    $container

# Skip installing and configuring the Firewall

# Copy the Pbench Server config file for our "in-a-can" environment.
buildah copy --chown pbench:pbench --chmod 0644 $container \
    ${PBINC_DIR}/etc/pbench-server/pbench-server.cfg ${CONF_PATH}

KEYCLOAK_CLIENT_SECRET=${KEYCLOAK_CLIENT_SECRET:-"client-secret"}

buildah run $container sed -Ei \
    -e "s/<keycloak_secret>/${KEYCLOAK_CLIENT_SECRET}/" \
    ${CONF_PATH}

buildah run $container mkdir -p -m 0755  \
    /srv/pbench/archive/fs-version-001 \
    /srv/pbench/public_html/dashboard \
    /srv/pbench/public_html/incoming \
    /srv/pbench/public_html/results \
    /srv/pbench/public_html/users \
    /srv/pbench/logs \
    /srv/pbench/tmp \
    /srv/pbench/pbench-move-results-receive/fs-version-002
buildah run $container cp /usr/share/nginx/html/404.html /usr/share/nginx/html/50x.html /srv/pbench/public_html/
buildah run $container chown --recursive pbench:pbench /srv/pbench

# Create the container image
buildah commit $container localhost/${PB_SERVER_IMAGE_NAME}:${PB_SERVER_IMAGE_TAG}
