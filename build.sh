#!/bin/bash -e

# This script drives the various tasks involved in testing and building the
# various artifacts for the Pbench product.  It is intended to be run from the
# root directory of a Git branch checkout.

# The following variables will normally be defined as credentials in the Jenkins
# environment.  For developer use of this script, they should be defined in the
# shell environment; otherwise, they will be given default values, here.
#
#  COPR_CONFIG - the path to the configuration file for the COPR account
#  PODMAN_USR - the username for the container registry account
#  PODMAN_PSW - the password for the container registry account
#
PODMAN_USR=${PODMAN_USR-"pbench+mr_jenkins"}
PODMAN_PSW=${PODMAN_PSW-${DEFAULT_PODMAN_PASSWORD}}
COPR_CONFIG=${COPR_CONFIG:-"${HOME}/.config/copr"}


# Function to read an initialization/configuration file and print the value of
# the specified key in the specified section.  Borrowed from
# https://stackoverflow.com/questions/49399984/parsing-ini-file-in-bash/49400353
function getIni() {
  local f=${1}  # Initialization/configuration file name
  local s=${2}  # Section name
  local o=${3}  # Option name

  if [[ ! -r ${f} ]]; then
    echo "Missing or bad COPR config file:  ${f}" >&2
    exit 1
  fi

  local rv=$(awk '/^\[.*\]$/{obj=$0}/=/{print obj $0}' ${f} | \
    sed -En "/${s}]${o}/s/^.*=[[:space:]]*//p" | \
    tail -n 1)

  if [[ -z ${rv} ]]; then
    echo "Missing '${o}' in COPR config file, '${f}'" >&2
    exit 1
  fi

  echo ${rv}
}


COPR_USER=$(getIni ${COPR_CONFIG} copr-cli username)
COPR_URL=$(getIni ${COPR_CONFIG} copr-cli copr_url)

if [[ ${COPR_URL} =~ "copr.fedorainfracloud.org" ]]; then
  URL_PREFIX=https://download.copr.fedorainfracloud.org/results/${COPR_USER}
elif [[ ${COPR_URL} =~ "copr.devel.redhat.com" ]]; then
  URL_PREFIX=http://coprbe.devel.redhat.com/results/${COPR_USER}
else
  echo "Unexpected COPR_URL: '${COPR_URL}'" >&2
  exit 1
fi

# Install the linter requirements and add them to the PATH.
export PATH=${HOME}/.local/bin:${PATH}
python3 -m pip install --user -r lint-requirements.txt

# If this script is run in a container and the user in the container doesn't
# match the owner of the Git checkout, then Git issues an error; these config
# settings avoid the problem.
GITTOP=$(git rev-parse --show-toplevel 2>&1 | head -n 1)
if [[ ${GITTOP} =~ "fatal: unsafe repository ('/home/root/pbench'" ]] ; then
	git config --global --add safe.directory /home/root/pbench
	git config --global --add safe.directory /home/root/pbench/agent/stockpile
	GITTOP=$(git rev-parse --show-toplevel)
fi

# Install the Dashboard dependencies, including the linter's dependencies and
# the unit test dependencies.
( cd dashboard && npm install )

# Test for code style and lint
black --check .
flake8 .
( cd dashboard && npx eslint "src/**" --max-warnings 0 )

# Run unit tests
tox                                     # Agent and Server unit tests and legacy tests
( cd dashboard && CI=true npm test )    # Dashboard unit tests

# Build Agent and Server RPMs (Server RPM includes the Dashboard) on COPR
( cd agent/rpm && make COPR_USER=${COPR_USER} COPR_CONFIG=${COPR_CONFIG} copr-ci )
( cd server/rpm && make COPR_USER=${COPR_USER} COPR_CONFIG=${COPR_CONFIG} copr-ci )

# The following steps don't work inside the CI container, so just declare
# victory now.  (Building a container inside a container requires a
# specially-configured and/or -invoked container, and we don't have that
# arranged, yet.)
exit 0

################################################################################
#  Future extensions
################################################################################

# Need to log into the registry to access the Server base image, etc.
podman login -u="${PODMAN_USR}" -p="${PODMAN_PSW}" quay.io

# Build the Agent container images and the Pbench-in-a-Can Server image
( cd agent/containers/images && \
  make COPR_USER=${COPR_USER} URL_PREFIX=${URL_PREFIX} TEST=ci \
  )
server/pbenchinacan/container-build.sh

# Push the Agent and Server container images to the container registry.
( cd agent/containers/images && \
  make COPR_USER=${COPR_USER} URL_PREFIX=${URL_PREFIX} TEST=ci tag-ci push-ci \
  )
podman push quay.io/pbench/pbenchinacan-pbenchserver
