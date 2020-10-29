# Fedora 32 pbench developement image
#
# We maintain this image with all the necessary user-space setup required to
# run the various unit tests and functional tests in a common development
# environment.
#
# The image is published to https://quay.io/pbench/development and "tagged"
# using the branch name in which it works: `master`, `b0.70`, `b0.71`, etc.
#
# NOTE WELL: This image has no entry point.
#
# It is intended to be built on top of with additional entry point for running
# a text or a suite in pbench.
#
# Also note that the pbench sources are not built into the image.  Instead
# we create a local directory, /mnt/pbench, to which one can mount an external
# directory containing the source tree.
#
# Build the image using:
#
#   $ buildah bud -f development.Dockerfile -t pbench-devel:<branch name>
#
# See https://www.redhat.com/sysadmin/user-flag-rootless-containers
# podman run -it --name pbench --userns=keep-id --volume $(pwd):/home/pbench:z --rm localhost/pbench-devel:jenkins /bin/bash -c 'tox -e lint'

FROM docker.io/library/fedora:32
RUN \
    dnf install -y python3-tox python3-pip python3-bottle python3-cffi python3-click python3-colorlog python3-daemon python3-redis python3-requests python3-sh python3-werkzeug python3-psutil bzip2 tar xz screen psmisc bc sos redis perl perl-JSON perl-JSON-XS perl-Time-HiRes perl-Data-UUID ansible hostname iproute iputils openssh-server openssh-clients rsync && \
    dnf -y clean all && \
    rm -rf /var/cache/dnf
