prog = netperf
version = 2.6.0
arch = x86_64

all: rpm rpm-copy

rpm: all-but-build build

all-but-build: check clean remotetar copy-patches

copy-patches:
	cp netperf-inline.patch ~/rpmbuild/SOURCES

include ${TOP}/rpm/misc-scripts/mk/rpm.mk
