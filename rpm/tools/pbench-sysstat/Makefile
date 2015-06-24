prog = pbench-sysstat
version = 11.1.2
arch = x86_64
PATCHES = Makefile.in.patch

all: rpm rpm-copy

rpm: all-but-build build

# order matters: spec-copy before pbench-sysstat-tar
all-but-build: check clean tar copy-patches

copy-patches:
	cp ${PATCHES} ~/rpmbuild/SOURCES

# impedance match: we repackage the tar ball with a different name and a different
# top level directory
tar: remotetar
	cd ~/rpmbuild/SOURCES &&\
	tar xf sysstat-${version}.tar.xz &&\
	mv sysstat-${version} pbench-sysstat-${version} &&\
	tar cf pbench-sysstat-${version}.tar.xz pbench-sysstat-${version} &&\
	rm -rf pbench-sysstat-${version} &&\
	rm -f  sysstat-${version}.tar.xz
	cd ~/rpmbuild/SPECS; sed -i '/Source0/s/sysstat/${prog}/' ${prog}.spec

include ${TOP}/rpm/misc-scripts/mk/rpm.mk
