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
# a test or a suite in pbench.
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
    dnf install -y ansible bc bzip2 diffutils git hostname iproute iputils less openssh-clients openssh-server perl perl-Data-UUID perl-JSON perl-JSON-XS perl-Time-HiRes procps-ng psmisc python3-boto3 python3-botocore python3-bottle python3-cffi python3-click python3-colorlog python3-daemon python3-elasticsearch python3-flask python3-humanize python3-jinja2 python3-flask-restful python3-gunicorn python3-itsdangerous python3-pip python3-psutil python3-redis python3-requests python3-s3transfer python3-sh python3-tox python3-tox-current-env python3-werkzeug redis rsync screen sos tar xz && \
    dnf -y clean all && \
    rm -rf /var/cache/dnf
