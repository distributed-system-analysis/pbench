#!/bin/bash -e

# This script drives the various tasks involved in testing and building the
# various artifacts for the Pbench product.  It is intended to be run from the
# root directory of a Git branch checkout.


# Install the linter requirements and add them to the PATH.
export PATH=${HOME}/.local/bin:${PATH}
python3 -m pip install --user -r lint-requirements.txt

# If this script is run in a container and the user in the container doesn't
# match the owner of the Git checkout, then Git issues an error; these config
# settings avoid the problem.
GITTOP=$(git rev-parse --show-toplevel 2>&1 | head -n 1)
if [[ ${GITTOP} = "fatal: unsafe repository ('/home/root/pbench'"* ]] ; then
	git config --global --add safe.directory /home/root/pbench
	GITTOP=$(git rev-parse --show-toplevel)
fi

# Install the Dashboard dependencies, including the linter's dependencies and
# the unit test dependencies.  First, remove any existing Node modules and
# package-lock.json to ensure that we install the latest.
make -C dashboard clean node_modules

# Test for code style and lint (echo the commands before executing them)
set -x
black --check .
flake8 .
isort --check .
make -C dashboard run_lint
# We need to invoke the alembic check with host networking so that it can reach
# the PostgreSQL pod it creates.
EXTRA_PODMAN_SWITCHES="--network host" jenkins/run tox -e alembic-migration -- check
set +x

# Run unit tests
tox                                     # Agent and Server unit tests and legacy tests
make -C dashboard run_unittests         # Dashboard unit tests

# Build RPMS for the Server and Agent and build the Dashboard deployment
make -C server/rpm distclean  # Cleans all RPMs, both Server and Agent.
make -C server/rpm ci
make -C agent/rpm ci
make -C dashboard build

# Display our victory
ls -l "${HOME}/rpmbuild*/RPMS/noarch/*"
