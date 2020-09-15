# Making a pbench-server RPM requires a few steps
# 1. Generate a version number
# 2. Update the RPM spec file with that version number
# 3. Generate a tar ball of the sources to be used by the RPM building process
# 4. Generate an SRPM that will be uploaded to COPR for building.

CWD = $(shell pwd -L)

SERVER = $(dir ${CWD})
PBENCHTOP = $(shell dirname ${SERVER})
TMPDIR = /var/tmp/pbench-server-package

VERSION = $(shell cat ${SERVER}/VERSION)

DISTRO = $(shell uname -r | python -c 'import sys; print(sys.stdin.read().split(".")[-2])')

ifeq (${DISTRO},el7)
PYTHON = scl enable rh-python36 -- python3
else
PYTHON = python3
endif

RPMSRC = ${HOME}/rpmbuild/SOURCES
RPMSRPM = ${HOME}/rpmbuild/SRPMS
RPMSPEC = ${HOME}/rpmbuild/SPECS

prog = pbench-server
arch = noarch

USE_GIT_SHA1 = yes
sha1 = $(shell git rev-parse --short HEAD)

all:
	echo Version: ${VERSION}
	echo Prog: ${prog}
	echo SHA1: ${sha1}
	echo ${PYTHON}

srpm:	spec patches tarball
	rm -f ${HOME}/rpmbuild/SRPMS/$(prog)-*.src.rpm
	rpmbuild -bs ${HOME}/rpmbuild/SPECS/$(prog).spec

rpm:  srpm
	rpmbuild -bb ${HOME}/rpmbuild/SPECS/${prog}.spec

.PHONY: spec
spec: ${prog}.spec
	utils/set-version-release ${VERSION} ${prog}.spec ${sha1} > ${RPMSPEC}/$<

###########################################################################
# make an SRPM using the upstream bits
rpm-upstream: all-but-build
	rm -f ${HOME}/rpmbuild/SRPMS/$(prog)-*.src.rpm
	rpmbuild -bs ${HOME}/rpmbuild/SPECS/$(prog).spec

all-but-build: ${RPMSPEC}/${prog}.spec patches

.PHONY: patches
patches:
	if [ -d ${CWD}/patches ] ;then cp ${CWD}/patches/* ${RPMSRC} ;fi

.PHONY: tarball
tarball:
	(cd ${PBENCHTOP}; ${PYTHON} setup.py install --prefix=${PBENCHTOP})
	mkdir -p ${TMPDIR}/${prog}-${VERSION}/server
	git rev-parse --short HEAD > ${TMPDIR}/${prog}-${VERSION}/server/SHA1
	if [ ! -f seqno ] ;then echo 1 ;else cat seqno ;fi > ${TMPDIR}/${prog}-${VERSION}/server/SEQNO
	cd ${PBENCHTOP}/server; make install-all DESTDIR=${TMPDIR}/${prog}-${VERSION}/server
	cd ${PBENCHTOP}/web-server; make install DESTDIR=${TMPDIR}/${prog}-${VERSION}/web-server
	tar zcf ${RPMSRC}/pbench-server-${VERSION}.tar.gz -C ${TMPDIR} ${prog}-${VERSION}
	rm -rf ${TMPDIR}

###########################################################################
# build RPMs in COPR
seqno := $(shell if [ -f seqno ] ;then cat seqno ;else echo 1; fi)

include utils/rpm.mk

clean-sha1:
	rm -f ${upstmtree}/${prog}.SHA1

clean:: localclean

