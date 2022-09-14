# Makefile for generating a source RPM and, optionally, binary RPMs
# for the Pbench server.

# To limit the builds to certain chroots or exclude certain chroots
# from building, add entries of the form
#    "--chroot centos-stream-9-x86_64"
# or
#    "--exclude-chroot centos-stream-9-x86_64"
# to the CHROOTS variable below.
# Multiple such entries can be added to be passed as options to
# `copr-cli build'.  By default, we build every chroot configured for
# the project.
# N.B. `copr-cli' flags an error if the value of a `--chroot' or
# `--exclude-chroot' option is not configured in the project.
# E.g. to build the RHEL9 chroots only:
# CHROOTS = --chroot centos-stream-9-x86_64 \
#           --chroot centos-stream-9-aarch64 \
#           --chroot epel-9-x86_64 \
#           --chroot epel-9-aarch64
CHROOTS = --chroot rhel-9.dev-x86_64
component = server
subcomps = server web-server

include ../../utils/rpm.mk

ci: rhel-9-rpm
