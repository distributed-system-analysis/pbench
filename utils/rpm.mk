#
# Common definitions for making an RPM, used by both the Agent and the Server.
#
# Making a pbench component RPM requires a few steps:
# 1. Get version number.
# 2. Update the RPM spec file with that version number etc.
# 3. Update any GIT submodules.
# 4. Do a "make install" to a temp directory.
# 5. Generate a tar ball from the directory.
# 6. Generate a local SRPM that can be uploaded to COPR for building.
# 7. Optionally generate a local RPM.
# 8. Clean up the temp directory
#
# In addition, specifying a distro-specific target, like "rhel-9-rpm", will
# cause Step 7 to be executed locally in a suitable container, to produce a
# binary RPM for the indicated distribution.  In this case, the RPM will be
# placed in ${HOME}/rpmbuild-<distro>-<version>/RPMS.
#

RPMBUILD_IMAGE_REPO = images.paas.redhat.com/pbench
BUILD_CONTAINER = ${RPMBUILD_IMAGE_REPO}/pbench-rpmbuild:${*}

PBENCHTOP := $(shell git rev-parse --show-toplevel)

# Include definition of _DISTROS, _space, etc.
include ${PBENCHTOP}/utils/utils.mk

prog = pbench-${component}
VERSION := $(shell cat ${PBENCHTOP}/${component}/VERSION)
MAJORMINOR := $(shell grep -oE '[0-9]+\.[0-9]+' ${PBENCHTOP}/${component}/VERSION)
TBDIR = ${RPMTMP}/${prog}-${VERSION}

# If we are building for a distro, use a distro-specific suffix on the build and
# temporary directories, so that builds can be done in parallel and so that the
# build products don't overwrite each other.
ifneq ($(findstring $(word 1,$(subst -,${_space},${MAKECMDGOALS})),${_ALL_DISTRO_NAMES}),)
  # Extract the distribution name and version from the first two fields, e.g.,
  # fedora-35-rpm would yield values "fedora" and "35" for DIST_NAME and
  # DIST_VERSION, respectively.
  DIST_NAME := $(word 1,$(subst -,${_space},${MAKECMDGOALS}))
  DIST_VERSION := $(word 2,$(subst -,${_space},${MAKECMDGOALS}))
  BLD_SUFFIX := -${DIST_NAME}-${DIST_VERSION}
else
  BLD_SUFFIX :=
endif

# Set BLD_DIR to `${BLD_ROOT}/rpmbuild-<DISTRO>-<VERSION>` when the target has
# a specific distro and to `${BLD_ROOT}/rpmbuild` when the target has no
# specific distro.  (Define BLD_SUBDIR separately from BLD_DIR to allow us to
# mix and match them for mapping the location into the container.)  This
# prevents builds for one distro from interfering with builds for another.
BLD_ROOT ?= ${HOME}
BLD_SUBDIR ?= rpmbuild${BLD_SUFFIX}
BLD_DIR := ${BLD_ROOT}/${BLD_SUBDIR}

RPMDIRS = BUILD BUILDROOT SPECS SOURCES SRPMS RPMS TMP

RPMSRC = ${BLD_DIR}/SOURCES
RPMSRPM = ${BLD_DIR}/SRPMS
RPMSPEC = ${BLD_DIR}/SPECS
RPMTMP = ${BLD_DIR}/TMP

sha1 := $(shell git rev-parse --short=9 HEAD)
seqno := $(shell if [ -e ./seqno ] ;then cat ./seqno ;else echo "1" ;fi)

$(info Building ${MAKECMDGOALS} for ${prog}-${VERSION} from ${TBDIR} to ${BLD_DIR})

# By default we only build a source RPM
all: srpm

.PHONY: rpm
rpm: spec srpm
	rpmbuild --define "_topdir ${BLD_DIR}" -bb ${RPMSPEC}/${prog}.spec

.PHONY: srpm
srpm: spec patches tarball
	rm -f ${RPMSRPM}/$(prog)-*.src.rpm
	rpmbuild --define "_topdir ${BLD_DIR}" -bs ${RPMSPEC}/${prog}.spec

.PHONY: spec
spec: rpm-dirs ${prog}.spec.j2
	if [ -e ./seqno ] ;then expr ${seqno} + 1 > ./seqno ;fi
	jinja2 ${prog}.spec.j2 -D version=${VERSION} -D gdist=g${sha1} -D seqno=${seqno} > ${RPMSPEC}/${prog}.spec
	cp ${PBENCHTOP}/utils/rpmlint ${RPMSPEC}/pbench-common.rpmlintrc
	XDG_CONFIG_HOME=${PBENCHTOP}/utils rpmlint ${RPMSPEC}/${prog}.spec

.PHONY: patches
patches: rpm-dirs
	if [ -d ./patches ] ;then cp ./patches/* ${RPMSRC}/ ;fi

.PHONY: tarball
tarball: rpm-dirs submodules ${subcomps}
	echo "${sha1}" > ${TBDIR}/${component}/SHA1
	echo "${seqno}" > ${TBDIR}/${component}/SEQNO
	tar zcf ${RPMSRC}/${prog}-${VERSION}.tar.gz -C ${RPMTMP} ${prog}-${VERSION}
	rm -rf ${RPMTMP}/*

.PHONY: rpm-dirs
rpm-dirs:
	mkdir -p $(addprefix ${BLD_DIR}/,${RPMDIRS})

.PHONY: submodules
submodules:
	cd ${PBENCHTOP} && git submodule update --init --recursive

.PHONY: ${subcomps}
${subcomps}:
	make -C ${PBENCHTOP}/$@ DESTDIR=${TBDIR}/$@ install

$(RPMSRPM)/$(prog)-$(VERSION)-$(seqno)g$(sha1).src.rpm: srpm

ifdef COPR_USER
_copr_user = ${COPR_USER}
else
_copr_user = ${USER}
endif

COPR_TARGETS = copr copr-test
.PHONY: ${COPR_TARGETS}
${COPR_TARGETS}: $(RPMSRPM)/$(prog)-$(VERSION)-$(seqno)g$(sha1).src.rpm
	copr-cli build ${CHROOTS} $(_copr_user)/$(subst copr,pbench-$(MAJORMINOR),$@) $(RPMSRPM)/$(prog)-$(VERSION)-$(seqno)g$(sha1).src.rpm

# Determine the present working directory relative to ${PBENCHTOP} so that we
# can find it inside the container, where the source tree might be in a
# different location.
pwdr = $(subst ${PBENCHTOP}/,,${CURDIR})

# This target is used to build RPMs for specific distros.  It launches a
# "normal" `rpm` target in a sub-make that is run inside a container built from
# the distro for which the RPM is targeted.  We override the definitions for
# `${BLD_ROOT}` and `${BLD_SUBDIR}` so that they point to the distro-specific
# directory inside the container.
#
# Each sub-make is self contained -- it builds its own SRPM and binary RPM --
# putting the output in the file system mapped in from the host.  So, the
# pattern target here only needs to create the output directories which will be
# mapped into the containers.
#
# TODO:  When building more than one container, we should probably build the
#        SRPM exactly once (on the host) and then map it into the container(s).
#        And, we should presumably share the values of $(VERSION), $(seqno),
#        and $(sha1), as well.
.PHONY: %-rpm
%-rpm: rpm-dirs
	cd ${PBENCHTOP} && \
	  IMAGE=${BUILD_CONTAINER} \
	    jenkins/run \
	      make BLD_ROOT=${BLD_ROOT} BLD_SUBDIR=${BLD_SUBDIR} -C ${pwdr} rpm

.PHONY: distclean
distclean:
	rm -rf $(addprefix ${BLD_ROOT}/rpmbuild*/,${RPMDIRS}) /tmp/rpmbuild*/opt

.PHONY: clean
clean:: rpm-clean

.PHONY: rpm-clean
rpm-clean:
	rm -rf $(foreach dir,${RPMDIRS},${BLD_ROOT}/rpmbuild*/${dir}/*)
