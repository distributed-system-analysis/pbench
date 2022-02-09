# Makefile for generating a source RPM and optional local RPM
# for the Pbench agent.

# To limit the builds to certain chroots or exclude certain chroots
# from building, add entries of the form
#    "--chroot centos-stream-9-x86_64"
# or
#    "--exclude-chroot centos-stream-9-x86_64"
# to the CHROOTS variable below.
# Multiple such entries can be added to be passed as options to
# `copr-cli build'.  By default, we build every chroot configured for
# the repo.
# N.B. `copr-cli' flags an error if the value of a `--chroot' or
# `--exclude-chroot' option is not configured in the repo.
# E.g. to build the RHEL9 chroots only:
# CHROOTS = --chroot centos-stream-9-x86_64 \
#           --chroot centos-stream-9-aarch64 \
#           --chroot epel-9-x86_64 \
#           --chroot epel-9-aarch64
# By default, we build every chroot enabled in the repo.
CHROOTS =

component = agent
subcomps = agent

include ../../utils/rpm.mk
