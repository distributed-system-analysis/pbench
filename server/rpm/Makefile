# Making a pbench-server RPM requires a few steps
# 1. Generate a version number
# 2. Update the RPM spec file with that version number
# 3. Generate a tar ball of the sources to be used by the RPM building process
# 4. Generate an SRPM that will be uploaded to COPR for building.

CWD = $(shell pwd -L)

component = server

PBENCHTOP := $(shell git rev-parse --show-toplevel)
VERSION := $(shell cat ${PBENCHTOP}/${component}/VERSION)
MAJORMINOR := $(shell grep -oE '[0-9]+\.[0-9]+' ${PBENCHTOP}/${component}/VERSION)

prog = pbench-server
arch = noarch

DISTRO = $(shell uname -r | python -c 'import sys; print(sys.stdin.read().split(".")[-2])')

PYTHON = python3

# temp directory for packing up the tarball
TMPDIR = /tmp/opt
TBDIR = ${TMPDIR}/${prog}-${VERSION}

USE_GIT_SHA1 = yes
sha1 := $(shell git rev-parse --short HEAD)
seqno := $(shell if [ -e ./seqno ] ;then cat ./seqno ;else echo "1" ;fi)

# By default we only build a source RPM
all: srpm

rpm: srpm
	rpmbuild -bb ${RPMSPEC}/${prog}.spec

srpm: spec patches tarball
	rm -f ${RPMSRPM}/${prog}-*.src.rpm
	rpmbuild -bs ${RPMSPEC}/${prog}.spec

.PHONY: spec
spec: ${prog}.spec.j2
	mkdir -p ${RPMSPEC}
	if [ -e ./seqno ] ;then expr ${seqno} + 1 > ./seqno ;fi
	jinja2 ${prog}.spec.j2 -D version=${VERSION} -D gdist=g${sha1} -D seqno=${seqno} > ${RPMSPEC}/${prog}.spec
	rpmlint ${RPMSPEC}/${prog}.spec

.PHONY: patches
patches:
	if [ -d ${CWD}/patches ] ;then cp ${CWD}/patches/* ${RPMSRC} ;fi

.PHONY: tarball
tarball:
	mkdir -p ${RPMSRC}
	make -C ${PBENCHTOP}/${component} DESTDIR=${TBDIR}/${component} install
	make -C ${PBENCHTOP}/web-server DESTDIR=${TBDIR}/web-server install
	echo "${sha1}" > ${TBDIR}/${component}/SHA1
	echo "${seqno}" > ${TBDIR}/${component}/SEQNO
	tar zcf ${RPMSRC}/${prog}-${VERSION}.tar.gz -C ${TMPDIR} ${prog}-${VERSION}
	rm -rf ${TMPDIR}

###########################################################################
# build RPMs in COPR

include rpm.mk

clean-sha1:
	rm -f ${upstmtree}/${prog}.SHA1

clean:: rpm-clean
