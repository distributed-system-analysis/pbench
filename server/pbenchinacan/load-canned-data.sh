#!/usr/bin/env -S bash -e

#
# This script loads a pre-defined set of tarballs into a Pbench server.
#
# If invoked with a single argument, it is assumed to be an authorization token;
# if invoked with two arguments, they are assumed to be a username/password
# pair; if invoked with no arguments, the username and password default to
# standard values.  If not invoked with a token, the username/password pair are
# used to generate a token.
#
# Using the standard Pbench Agent config file (via the _PBENCH_AGENT_CONFIG
# environment variable), this script repeatedly invokes pbench-results-push to
# push a select set of tarballs from the Server validation tests to the target
# server.
#

src=${PWD}/server/bin/state
tmp=${TMPDIR:-/var/tmp}/load_canned_data

if [[ ! -e ${src} ]]
then
  echo "Cannot find source directory (the current directory must be the repository root)."
  exit 2
fi

rm -rf ${tmp} || :  # Remove the temporary directory if it exists or ignore it
if ! mkdir -p "${tmp}"
then
  echo "Cannot create temporary directory, '${tmp}'" >&2
  exit 2
fi

if [[ $# == 1 ]]
then
  token=$1
else
  username=${1:-pbench_user}
  password=${2:-pbench}
  token=$(pbench-generate-token --username $username --password $password)
fi

# We skip test-7.8, test-7.12, and test-7.15, which have controllers that are
# not legal nodenames, so the server refuses to accept them.  We skip test-7.14,
# which has a tarball with the same name as test-7.13, although it has different
# contents.  We skip test-7.18, which has a mismatched controller in its
# metadata.  And, we skip test-7.26 which appears to have the same tarball as
# test-7.22.
tests="test-7.9 test-7.10 test-7.11 test-7.13 test-7.16 test-7.17 test-7.19"
tests+=" test-7.20 test-7.21 test-7.22 test-7.23 test-7.24 test-7.25"

echo "Extracting tarballs"
for test_name in ${tests}; do
  tar -x -C ${tmp} -f ${src}/${test_name}.tar.xz
done

for ctlr_dir in ${tmp}/pbench/archive/fs-version-001/*; do
  for tarball in ${ctlr_dir}/*.tar.xz; do
    echo "Pushing $(basename ${ctlr_dir}) $(basename ${tarball}):"
    pbench-results-push --token ${token} $(basename ${ctlr_dir}) ${tarball}
  done
done

rm -rf ${tmp}

# Notes:
#
# Two of the tarballs appear twice:
#  - test-7.13 and test-7.14:
#      b03-h01-1029p/pbench-user-benchmark_mbruzek-test-2_2018.04.10T19.01.19.tar.xz
#      and the contents are different.
#  - test-7.22 and test-7.26:
#      ctlrA/linpack_mock_2020.02.28T19.10.55.tar.xz
#      and the contents are the same.
#
# The indexer reports "sample_missing_timeseries" errors:
#  - test-7.19: perf122/trafficgen_basic-forwarding-example_tg:trex-profile_pf:forwarding_test.json_ml:5_tt:bs__2019-08-27T14:58:38.tar.xz
#  - test-7.21: ctlrA/trafficgen_mock_2020.02.28T19.49.39.tar.xz
#  - test-7.21: ctlrA/trafficgen_mock_2020.02.28T20.04.29.tar.xz
#  - test-7.26: ctlrA/linpack_mock_2020.02.28T19.10.55.tar.xz
#
# The indexer reports the following warnings about test-7.21:
#   No [tools] section in metadata.log: tool data will *not* be indexed (ctlrA/trafficgen_mock_2020.02.28T19.49.39.tar.xz(ea6b84aa5a882a4e42ee11f7798fb40b))
#   No [tools] section in metadata.log: tool data will *not* be indexed (ctlrA/trafficgen_mock_2020.02.28T20.04.29.tar.xz(b683a7a6756abc8f9bff4bddb5679d2c))
#
# The indexer reports the following errors with test-7.18 (so we don't upload it):
#   Bad metadata.log file encountered: bad-controller/pbench-user-benchmark__2018.02.05T20.35.36.tar.xz - error fetching required metadata.log fields, "No section: 'run'"
#   Bad metadata.log file encountered: bad-controller/test_7.18_2018.02.05T15.31.08.tar.xz - error fetching required metadata.log fields, "run.controller ("alphaville.example.com") does not match controller_dir ("bad-controller")"
#
