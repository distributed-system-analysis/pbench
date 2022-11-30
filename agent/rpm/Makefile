# Makefile for generating a source RPM and, optionally, binary RPMs
# for the Pbench agent.

# When building a binary RPM on COPR, to limit the builds to certain chroots
# or to exclude certain chroots from building, add entries of the form
#    "--chroot centos-stream-9-x86_64"
# or
#    "--exclude-chroot centos-stream-9-x86_64"
# to the definition of the CHROOTS variable.
#
# Multiple such entries can be added to be passed as options to
# `copr-cli build'.  N.B. `copr-cli' flags an error if the value of a
# `--chroot' or `--exclude-chroot' option is not configured in the repo.
# E.g. to build the RHEL9 chroots only:
# CHROOTS = --chroot centos-stream-9-x86_64 \
#           --chroot centos-stream-9-aarch64 \
#           --chroot epel-9-x86_64 \
#           --chroot epel-9-aarch64
#
# Unless overridden on the command line, build every chroot enabled in the repo.
CHROOTS =

# These targets build the binary RPM for the specified distro version; the "ci"
# target builds them all.
RHEL_RPMS = rhel-9-rpm rhel-8-rpm rhel-7-rpm
CENTOS_RPMS = centos-9-rpm centos-8-rpm centos-7-rpm
FEDORA_RPMS = fedora-36-rpm fedora-35-rpm
ALL_RPMS = ${RHEL_RPMS} ${CENTOS_RPMS} ${FEDORA_RPMS}

component = agent
subcomps = agent

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

export  # Export the definitions above in the invocation of the sub-make.

# For historical compatibility, this is the default target.
all: srpm

# For the CI, we build all of our favorite RPMs, but we do that via the
# dependency list rather than by any immediate action.  There are two things
# happening here:  first, the dependencies can be built in parallel if the
# invocation permits it, e.g., 'make -j 4 -O ci'; second, rpm.mk, when it is
# invoked, determines which distro to build for based on the pattern of the
# specified target, so we need to invoke it separately for each one, because
# having multiple targets in the same invocation for different distributions
# won't work.
ci: ${ALL_RPMS} ;

# This is a catch-all rule which forwards any target that we don't handle in
# this makefile on to the common makefile.
%: FORCE
	@$(MAKE) --makefile ../../utils/rpm.mk $@

# This recipe does nothing, other than to force the previous one to run.
FORCE: ;

# This recipe does nothing, other than to avoid running the catch-all recipe
# when Make does the implicit Makefile target check.
Makefile ../../utils/utils.mk: ;
