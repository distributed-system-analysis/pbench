CWD = $(shell pwd)

prog = pbench-report
version  = 0.01
srctree = ${TOP}/web-server
USE_GIT_SHA1 = yes

all: rpm rpm-copy

rpm: all-but-build build

all-but-build: check clean tar

clean::
	rm -f ${srctree}/${prog}/file.list ${srctree}/$(prog)-$(version)

tar:	rpm-dirs file.list
	cd ${srctree}; rm -f $(prog)-$(version); ln -sf $(prog) $(prog)-$(version);\
	  tar -X ${CWD}/$(prog).rpm.exclude \
	      -zchf ${HOME}/rpmbuild/SOURCES/$(prog)-$(version).tar.gz $(prog)-$(version)
	rm -f $(prog)-$(version)

.PHONY:
file.list:
	cd ${srctree}/${prog}; find . -type f | grep -v -f ${CWD}/$(prog).rpm.exclude > $@

include ${TOP}/rpm/misc-scripts/mk/rpm.mk

test:
	echo ${version}
