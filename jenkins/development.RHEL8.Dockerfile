# RHEL 8 pbench development image
#
# We maintain this image with all the necessary user-space setup required to
# run the various unit tests and functional tests in a common development
# environment.  However, in certain instances, the tests require specific
# versions of software packages (Black and Flake8 being notable examples),
# and these cannot always be satisfied by the RPMs available from the
# distribution.  In these cases, we expect the packages to be installed at
# run-time.  Nevertheless, in order to avoid run-time installations where
# possible, we install indirect dependencies of the run-time installations
# below, as well.
#
# The image is published to https://quay.io/pbench/development and "tagged"
# using the branch name in which it works: `master`, `b0.70`, `b0.71`, etc.
#
# NOTE WELL: This image inherits its entry point from the base image --
# /sbin/init -- which allows systemctl-enabled daemons to run automatically.
#
# You can use this image to run our development environment from a command
# line, e.g.:
#
#  $ podman run -it --rm pbench-devel:<branch name> /bin/bash
#
# which will allow you to run a RHEL 8 pbench development environment.
# Or you can use this image as a base image, and build another image on top
# of it to run your own end-points.
#
# Also note that the pbench sources are not built into the image.  Instead
# they should be mounted as a local directory, e.g., /src/pbench, using an
# external directory [1] containing the source tree.
#
# Build the image using (see jenkins/Makefile):
#
#   $ buildah bud -f development.Dockerfile -t pbench-devel:<branch name>
#
# Run tests using (see jenkins/run and jenkins/Pipeline.gy):
#
#   $ podman run -it --userns=keep-id --volume $(pwd):/src/pbench:z \
#     --rm localhost/pbench-devel:<branch name> \
#     "source jenkins/python-setup.sh; jenkins/run-pytests; jenkins/run-unittests"
#
# Note that building this image uses the IntLab DNF repos, the list of which it
# pulls from https://code.engineering.redhat.com/gerrit/plugins/gitiles/perf-dept/+/refs/heads/master/sysadmin/IntegrationLab/Ansible/intlab.repo
# Accessing these requires that the IntegrationLab DNF repo mirror nodes'
# addresses be resolvable.  If they are inaccessible on the host system, they
# can be added to /etc/hosts via:
#
#   cat >>/etc/hosts <<< "10.1.170.92 mirror01.intlab.redhat.com"
#   cat >>/etc/hosts <<< "10.1.170.94 mirror02.intlab.redhat.com"
#
# [1] See https://www.redhat.com/sysadmin/user-flag-rootless-containers

FROM registry.access.redhat.com/ubi8/ubi-init:8.4

# Install the PGP keys and anything else that we keep cached copies of.
COPY ./etc/ /etc/

RUN \
    curl -sSk -o /etc/yum.repos.d/intlab.repo \
        http://git.app.eng.bos.redhat.com/git/perf-dept.git/plain/sysadmin/IntegrationLab/Ansible/intlab.repo && \
    dnf install -y \
        `#` \
        `# Install the EPEL repo` \
        `#` \
        https://dl.fedoraproject.org/pub/epel/epel-release-latest-8.noarch.rpm \
        \
        `#` \
        `# Install Agent dependencies` \
        `#` \
        `# This list should be generated via 'dnf -q repoquery --requires <RPM>'` \
        `# using the Agent RPM.  Then, if a 'pip3 install -r requirements.txt'` \
        `# shows any missing dependencies they should be added to the RPM spec` \
        `# file and this list should be regenerated.` \
        `#` \
        ansible \
        bc \
        bzip2 \
        hostname \
        iproute \
        iputils \
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
        python3 \
        python3-cffi \
        python3-click \
        python3-docutils \
        python3-pip \
        python3-psutil \
        python3-requests \
        python3-sh \
        redis \
        rpmdevtools \
        rsync \
        screen \
        sos \
        tar \
        xz \
        \
        `#` \
        `# Install Server dependencies` \
        `#` \
        `# This list should be generated via 'dnf -q repoquery --requires <RPM>'` \
        `# using the Server RPM.  Then, if a 'pip3 install -r requirements.txt'` \
        `# shows any missing dependencies they should be added to the RPM spec` \
        `# file and this list should be regenerated.` \
        `#` \
        cronie \
        npm \
        policycoreutils \
        policycoreutils-python-utils \
        python3 \
        python3-alembic \
        python3-aniso8601 \
        python3-bcrypt \
        python3-boto3 \
        python3-certifi \
        python3-click \
        python3-dateutil \
        python3-devel \
        python3-elasticsearch \
        python3-email-validator \
        python3-flask \
        python3-flask-cors \
        python3-flask-migrate \
        python3-flask-restful \
        python3-flask-sqlalchemy \
        python3-greenlet \
        python3-gunicorn \
        python3-humanize \
        python3-libselinux \
        python3-psycopg2 \
        python3-requests \
        python3-sqlalchemy \
        \
        `#` \
        `# Install common lint and testing dependencies` \
        `#` \
        `# Note that the versions of Black and Flake8 are almost certainly` \
        `# wrong, but, if so, the setup will install the proper versions.` \
        `# The packages in this list other than Black and Flake8 cover their` \
        `# dependencies when installed via pip.` \
        `#` \
        python3-flake8 \
        python3-toml \
        python3-regex \
        python3-typed_ast \
        python3-pathspec \
        python3-attrs \
        python3-appdirs \
        python3-entrypoints \
        python3-pycodestyle \
        python3-mccabe \
        python3-pyflakes \
        \
        `#` \
        `# Install Agent testing dependencies` \
        `#` \
        python3-coverage \
        python3-GitPython \
        python3-mock \
        python3-pytest \
        python3-pytest-cov \
        python3-pytest-mock \
        python3-responses \
        `#` \
        `# These two packages are dependencies of the pip-installed PyTest` \
        `# package; when we switch to the RPM-installed version, we should` \
        `# drop them.` \
        `#` \
        python3-atomicwrites \
        python3-wcwidth \
        \
        `#` \
        `# Install Server testing dependencies` \
        `#` \
        python3-coverage \
        python3-GitPython \
        python3-mock \
        python3-pytest \
        python3-pytest-cov \
        python3-pytest-mock \
        python3-requests-mock \
        python3-responses \
        \
        `#` \
        `# Install Docs dependencies` \
        `#` \
        python3-sphinx \
        \
        `#` \
        `# Install utilities for building RPMs, evaluating test results, etc.` \
        `#` \
        copr-cli \
        diffutils \
        git \
        less \
        `# python3-jinja2-cli` \
        python3-wheel \
        rpmlint \
        rpm-build \
        sqlite && \
        \
        `#` \
        `# Save space in the container image.` \
        `#` \
        dnf -y clean all && rm -rf /var/cache/dnf
