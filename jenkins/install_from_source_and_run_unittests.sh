#!/bin/bash -e

# This script is intended to be run as root inside a container in a working
# directory containing a Git checkout of the Pbench sources (which should NOT
# be `/home/pbench`).  It builds RPMs for the Agent and Server, and then it
# installs them.  It assumes that the Server installation will create a
# `pbench` user account and a `/home/pbench` directory as the `$HOME` for the
# account.  Finally, it invokes `jenkins/run-unittests` under the `pbench`
# login after setting the working directory back to the one where this script
# was invoked (because the `su -l` will have changed it).  The output from
# each step is captured in files in `/tmp`.

(cd agent/rpm/ && make rpm) |& tee /tmp/pb-rpm-build-agent.out
(cd server/rpm/ && make rpm) |& tee /tmp/pb-rpm-build-server.out
dnf install -y /root/rpmbuild/RPMS/noarch/pbench-* |& tee /tmp/pb-rpm-install.out
su -lc "cd ${PWD} && jenkins/run-unittests" pbench |& tee /tmp/pb-run-unittests.out
