prog = uperf
version = 1.0.4
arch = x86_64

all: rpm rpm-copy

rpm: all-but-build build

all-but-build: check clean remotetar copy-patches

copy-patches:
	cp uperf.patch uperf-service.patch ~/rpmbuild/SOURCES

include ${TOP}/rpm/misc-scripts/mk/rpm.mk
