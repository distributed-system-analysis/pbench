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

include ../../utils/utils.mk

# Generate a sequence number to be used for the RPMs:  by default, the number
# will be 1; if the ./seqno file exists, use the number from the file and then
# increment it.  However, do this only if `seqno` is not already defined, and
# use a "simple assignment" to ensure that it is not incremented more than once.
# ("Conditional assignment" (?=) apparently produces a "recursive assignment",
# which gets re-evaluated each time the variable is referenced, which results in
# multiple increments.)
ifeq ($(origin seqno), undefined)
  seqno := $(call get_sequence_number,./seqno)
endif

include ../../utils/rpm.mk

ci: rhel-8-rpm
