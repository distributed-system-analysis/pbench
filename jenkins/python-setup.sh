#!/bin/bash

# This script sets up the Python environment for executing unit tests
# (particularly in a containerized environment).
#
# This script installs the Pbench requirements; however, the expectation is that
# all requirements will have been satisfied by previously-installed RPMs, so
# this step serves mostly to verify that assertion.  This script also invokes
# the project setup.py file which creates and installs the `pbench` Python-based
# command scripts.  The two installations are performed with the `--user`
# switch which ensures that their results land where Python will look for them
# implicitly.  Therefore, it revokes any existing definition of PYTHONPATH, to
# prevent other pbench installations from being found inadvertently.  Finally,
# this script adds the directory containing the locally-installed pbench
# commands to the front of the path (actually, this is done first to quiet
# warnings from the installations) to ensure that the current versions are
# chosen over any installed ones, and it adds `/usr/sbin` to the end of the
# path for the `ip` command, used by pbench-register-tool.

PATH=$(python3 -m site --user-base)/bin:${PATH}:/usr/sbin
unset PYTHONPATH
pip3 install --user -r lint-requirements.txt -r docs/requirements.txt -r agent/requirements.txt -r server/requirements.txt -r agent/test-requirements.txt -r server/test-requirements.txt
python3 setup.py develop --user
