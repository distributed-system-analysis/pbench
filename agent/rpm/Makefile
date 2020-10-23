# Making a pbench-agent RPM requires a few steps:
# 1. Get version number.
# 2. Update the RPM spec file with that version number etc.
# 3. Update the stockpile  submodule.
# 4. Do a "make install" of the agent to a temp directory.
# 5. Generate a tar ball from the directory.
# 6. Generate a local SRPM that will be uploaded to COPR for building.
# 7. Optionally generate a local RPM.
# 8. Clean up the temp directory

CWD = $(shell pwd)

# adjust as necessary
AGENT = $(dir ${CWD})

VERSION = $(file < ${AGENT}/VERSION)

# temp directory for packing up the tarball
TMPDIR = /tmp/opt

RPMSRC = ${HOME}/rpmbuild/SOURCES
RPMSRPM = ${HOME}/rpmbuild/SRPMS
RPMSPEC = ${HOME}/rpmbuild/SPECS

prog = pbench-agent
arch = noarch

USE_GIT_SHA1 = yes
sha1 := $(shell git rev-parse --short HEAD)
seqno := $(shell if [ -e ./seqno ] ;then cat ./seqno ;else echo "1" ;fi)

# By default we only build a source RPM
all: srpm

rpm: srpm
	rpmbuild -bb ${RPMSPEC}/${prog}.spec

srpm: spec patches tarball
	rm -f ${RPMSRPM}/$(prog)-*.src.rpm
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
	git submodule init
	git submodule update
	make -C .. DESTDIR=${TMPDIR}/${prog}-${VERSION}/agent
	echo "${sha1}" > ${TMPDIR}/${prog}-${VERSION}/agent/SHA1
	echo "${seqno}" > ${TMPDIR}/${prog}-${VERSION}/agent/SEQNO
	tar zcf ${RPMSRC}/pbench-agent-${VERSION}.tar.gz -C ${TMPDIR} ${prog}-${VERSION}
	rm -rf ${TMPDIR}

include rpm.mk

clean:: rpm-clean
