# Making a pbench-agent RPM requires a few steps:
# 1. Get version number.
# 2. Update the RPM spec file with that version number etc.
# 3. Update the stockpile  submodule.
# 4. Do a "make install" of the agent to a temp directory.
# 5. Generate a tar ball from the directory.
# 6. Generate a local SRPM that will be uploaded to COPR for building.
# 7. Optionally generate a local RPM.
# 8. Clean up the temp directory

# Do not use the RHEL9 chroots - v0.69 does not work on RHEL9
#CHROOTS = --exclude-chroot centos-stream-9-aarch64 \
#	  --exclude-chroot centos-stream-9-x86_64 \
#	  --exclude-chroot epel-9-aarch64 \
#	  --exclude-chroot epel-9-x86_64

CWD = $(shell pwd -L)

component = agent

PBENCHTOP := $(shell git rev-parse --show-toplevel)
VERSION := $(shell cat ${PBENCHTOP}/${component}/VERSION)
MAJORMINOR := $(shell grep -oE '[0-9]+\.[0-9]+' ${PBENCHTOP}/${component}/VERSION)

prog = pbench-agent
arch = noarch

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
	git submodule init
	git submodule update
	make -C ${PBENCHTOP}/${component} DESTDIR=${TBDIR}/${component}
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
