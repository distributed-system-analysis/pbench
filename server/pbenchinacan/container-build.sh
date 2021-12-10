#!/usr/bin/env bash
#
# This script builds a container which, when run, starts a Pbench Server.
#
# Note:  successfully running this script required adding AUDIT_WRITE (for the
#        operation of sshd) and CAP_SETFCAP (for the installation of httpd) to
#        the list of default capabilities in /etc/containers/containers.conf
#        (and, if that file doesn't exist, you'll need to create it with the
#        other default capabilities, e.g., see
#        https://man.archlinux.org/man/containers.conf.5.en#CONTAINERS_TABLE and
#        https://github.com/containers/common/blob/da56e470c0c57c27e91bdc844b32c5dab6611394/pkg/config/containers.conf#L48)
#

set -o errexit

# Locations inside the container
INSTALL_ROOT=/opt/pbench-server
SERVER_LIB=${INSTALL_ROOT}/lib
SERVER_BIN=${INSTALL_ROOT}/bin
CONF_PATH=${SERVER_LIB}/config/pbench-server.cfg
HOSTNAME_F=pbenchinacan

# Locations on the host
GITTOP=${GITTOP:-$(git rev-parse --show-toplevel)}
PBINC_DIR=${GITTOP}/server/pbenchinacan

# Open a copy of the base container.  Docker format is required in order to set
# the hostname.
container=$(buildah from --format=docker quay.io/pbench/pbench-devel-rhel8:main)

# We could mount the container filesystem and access it directly, but we
# instead access it with buildah commands.
# mnt=$(buildah mount $container)

# Consider adding -v datavolume for the Server data, and perhaps SQL and ES data
buildah config \
    --label maintainer="Nick Dokos <ndokos@redhat.com>" \
    --hostname $HOSTNAME_F \
    --stop-signal SIGINT \
    --port 22:55555  `# sshd` \
    --port 8001      `# pbench-server` \
    $container

# Set up Pbench DNF repo and install the Server and Apache
buildah copy $container ${PBINC_DIR}/etc/yum.repos.d/pbench.repo /etc/yum.repos.d/pbench.repo
buildah run $container dnf install -y pbench-server httpd
buildah run $container dnf clean all

# Skip installing and configuring the Firewall

# Work around a problem with cron running jobs as other users in a container
# FIXME:  it's unclear whether abusing anything other than crond's file helps.
buildah run $container bash -c "sed -i -e '/pam_loginuid/ s/^/#/' /etc/pam.d/*"

# Copy the Pbench Server config file; then correct the hostname configuration.
buildah copy --chown pbench:pbench --chmod 0644 $container \
    ${PBINC_DIR}/etc/pbench-server/pbench-server.cfg ${CONF_PATH}
buildah run $container sed -Ei \
    -e "/^default-host[[:space:]]*=/ s/=.*/= ${HOSTNAME_F}/" ${CONF_PATH}

buildah run $container su -l pbench \
    -c "_PBENCH_SERVER_CONFIG=${CONF_PATH} PATH=$SERVER_BIN:$PATH pbench-server-activate-create-crontab ${SERVER_LIB}/crontab"

buildah run $container mkdir -p -m 0755  \
    /srv/pbench/archive/fs-version-001 \
    /srv/pbench/public_html/incoming \
    /srv/pbench/public_html/results \
    /srv/pbench/public_html/users \
    /srv/pbench/public_html/static \
    /srv/pbench/logs \
    /srv/pbench/tmp \
    /srv/pbench/quarantine \
    /srv/pbench/pbench-move-results-receive/fs-version-002
buildah run $container chown --recursive pbench:pbench /srv/pbench

# SELinux is currently disabled inside the container, so these commands don't
# work very well, so we'll just comment them out for the time being.
#
# buildah run $container semanage fcontext -a -t httpd_sys_content_t /srv/pbench/archive
# buildah run $container semanage fcontext -a -t httpd_sys_content_t /srv/pbench/archive/fs-version-001
# buildah run $container semanage fcontext -a -t httpd_sys_content_t /srv/pbench/public_html/incoming
# buildah run $container semanage fcontext -a -t httpd_sys_content_t /srv/pbench/public_html/results
# buildah run $container semanage fcontext -a -t httpd_sys_content_t /srv/pbench/public_html/users
# buildah run $container semanage fcontext -a -t httpd_sys_content_t /srv/pbench/public_html/static
# buildah run $container restorecon -v -r /srv/pbench/archive /srv/pbench/public_html

buildah run $container crontab -u pbench ${SERVER_LIB}/crontab/crontab

echo >/tmp/pbench.conf.${$} \
"<VirtualHost *:80>
    ProxyPreserveHost On
    ProxyPass /api/ http://${HOSTNAME_F}:8001/api/
    ProxyPassReverse /api/ http://${HOSTNAME_F}:8001/api/
    ProxyPass / !
</VirtualHost>"
buildah copy --chown root:root --chmod 0644 $container \
    /tmp/pbench.conf.${$} /etc/httpd/conf.d/pbench.conf
rm /tmp/pbench.conf.${$}

buildah run $container cp ${SERVER_LIB}/systemd/pbench-server.service \
    /etc/systemd/system/pbench-server.service

buildah run $container systemctl enable httpd
buildah run $container systemctl enable pbench-server

# Create the container image
buildah commit $container pbench-server:latest
