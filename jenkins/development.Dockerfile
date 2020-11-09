# Fedora 32 pbench development image
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
# You can use this image to run our development environment from a command
# line, e.g.:
#
#  $ podman run -it --rm pbench-devel:<branch name> /bin/bash
#
# which will allow you to run a Fedora 32 pbench development environment.
# Or you can use this image as a base image, and build another image on top
# of it to run your own end-points.
#
# Also note that the pbench sources are not built into the image.  Instead
# we create a local directory, /home/pbench, to which one can mount an
# external directory [1] containing the source tree.
#
# Build the image using:
#
#   $ buildah bud -f development.Dockerfile -t pbench-devel:<branch name>
#
# Run tests using:
#
#   $ podman run -it --userns=keep-id --volume $(pwd):/home/pbench:z \
#     --rm localhost/pbench-devel:<branch name> /bin/bash -c 'tox -e lint'
#
# [1] See https://www.redhat.com/sysadmin/user-flag-rootless-containers

FROM docker.io/library/fedora:32
RUN \
    dnf install -y \
        ansible \
        bc \
        black \
        bzip2 \
        diffutils \
        git \
        hostname \
        iproute \
        iputils \
        less \
        net-tools \
        openssh-clients \
        openssh-server \
        perl \
        perl-Data-UUID \
        perl-JSON \
        perl-JSON-XS \
        perl-Time-HiRes \
        procps-ng \
        psmisc \
        python3-GitPython \
        python3-boto3 \
        python3-botocore \
        python3-bottle \
        python3-cffi \
        python3-click \
        python3-coverage \
        python3-daemon \
        python3-elasticsearch \
        python3-flake8 \
        python3-flask \
        python3-flask-restful \
        python3-gitdb \
        python3-gunicorn \
        python3-humanize \
        python3-itsdangerous \
        python3-jinja2 \
        python3-mock \
        python3-pip \
        python3-psutil \
        python3-pytest \
        python3-pytest-cov \
        python3-pytest-helpers-namespace \
        python3-pytest-mock \
        python3-redis \
        python3-requests \
        python3-responses \
        python3-s3transfer \
        python3-sh \
        python3-smmap \
        python3-tox \
        python3-tox-current-env \
        python3-werkzeug \
        redis \
        rsync \
        screen \
        sos \
        tar \
        xz \
        && \
    dnf -y clean all && \
    rm -rf /var/cache/dnf
