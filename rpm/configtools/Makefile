CWD = $(shell pwd)

prog = configtools
srctree = ${TOP}/$(prog)

# make sure that we can get to configtools.py even if it is not installed
# or if an older, less capable version is installed.
version = $(shell python ${srctree}/setup.py --version)

all: rpm rpm-copy

rpm: all-but-build build

all-but-build: check clean tar

.PHONY: tar
tar: rpm-dirs
	(cd ${srctree}; make prep-for-rpm)
	cd ${HOME}/rpmbuild; rm -f $(prog)-$(version); ln -s ${srctree}/build $(prog)-$(version); \
	  tar -X ${CWD}/$(prog).rpm.exclude \
	      -zchf ${HOME}/rpmbuild/SOURCES/$(prog)-$(version).tar.gz $(prog)-$(version)
	rm -f ${HOME}/rpmbuild/$(prog)-$(version)

include ${TOP}/rpm/misc-scripts/mk/rpm.mk
