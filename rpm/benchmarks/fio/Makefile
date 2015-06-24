prog = fio
version = 2.2.5
arch = x86_64

all: rpm rpm-copy

rpm: all-but-build build

all-but-build: check clean remotetar copy-patches

copy-patches:
	cp patches/* ${HOME}/rpmbuild/SOURCES

include ${TOP}/rpm/misc-scripts/mk/rpm.mk
