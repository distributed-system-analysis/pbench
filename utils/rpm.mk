# Common definitions for making an RPM, used by both the Agent and the Server.
#
# Making a pbench component RPM requires a few steps:
# 1. Get version number.
# 2. Update the RPM spec file with that version number etc.
# 3. Update any GIT submodules.
# 4. Do a "make install" to a temp directory.
# 5. Generate a tar ball from the directory.
# 6. Generate a local SRPM that will be uploaded to COPR for building.
# 7. Optionally generate a local RPM.
# 8. Clean up the temp directory

PBENCHTOP := $(shell git rev-parse --show-toplevel)
TMPDIR = /tmp/opt

prog = pbench-${component}
VERSION := $(file < ${PBENCHTOP}/${component}/VERSION)
TBDIR = ${TMPDIR}/${prog}-${VERSION}

RPMDIRS = BUILD BUILDROOT SPECS SOURCES SRPMS RPMS

RPMSRC = ${HOME}/rpmbuild/SOURCES
RPMSRPM = ${HOME}/rpmbuild/SRPMS
RPMSPEC = ${HOME}/rpmbuild/SPECS

sha1 := $(shell git rev-parse --short HEAD)
seqno := $(shell if [ -e ./seqno ] ;then cat ./seqno ;else echo "1" ;fi)

# By default we only build a source RPM
all: srpm

.PHONY: rpm
rpm: spec srpm
	rpmbuild -bb ${RPMSPEC}/${prog}.spec

.PHONY: srpm
srpm: spec patches tarball
	rm -f ${RPMSRPM}/$(prog)-*.src.rpm
	rpmbuild -bs ${RPMSPEC}/${prog}.spec

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
	tar zcf ${RPMSRC}/${prog}-${VERSION}.tar.gz -C ${TMPDIR} ${prog}-${VERSION}
	rm -rf ${TMPDIR}/*

.PHONY: rpm-dirs
rpm-dirs:
	mkdir -p $(addprefix ${HOME}/rpmbuild/,${RPMDIRS})

.PHONY: submodules
submodules:
	git submodule update --init --recursive

.PHONY: ${subcomps}
${subcomps}:
	make -C ${PBENCHTOP}/$@ DESTDIR=${TBDIR}/$@ install

$(RPMSRPM)/$(prog)-$(version)-$(seqno)g$(sha1).src.rpm: srpm

ifdef COPR_USER
_copr_user = ${COPR_USER}
else
_copr_user = ${USER}
endif

COPR_TARGETS = copr copr-test
.PHONY: ${COPR_TARGETS}
${COPR_TARGETS}: $(RPMSRPM)/$(prog)-$(version)-$(seqno)g$(sha1).src.rpm
	copr-cli build ${CHROOTS} $(_copr_user)/$(subst copr,pbench,$@) $(RPMSRPM)/$(prog)-$(VERSION)-$(seqno)g$(sha1).src.rpm

.PHONY: distclean
distclean:
	rm -rf $(addprefix ${HOME}/rpmbuild/,${RPMDIRS})

.PHONY: clean
clean:: rpm-clean

.PHONY: rpm-clean
rpm-clean:
	rm -rf $(foreach dir,${RPMDIRS},${HOME}/rpmbuild/${dir}/*)
