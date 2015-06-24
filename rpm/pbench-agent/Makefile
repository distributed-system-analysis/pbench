CWD = $(shell pwd)

srctree = ${TOP}/agent
prog = pbench-agent
# make sure that we can get to configtools.py even if it is not installed
version = $(shell PYTHONPATH=${TOP}/configtools/build/lib:$$PYTHONPATH PATH=${TOP}/configtools/build/bin:$$PATH getconf.py version ${prog})
arch = noarch

USE_GIT_SHA1 = yes

all: rpm rpm-copy

rpm: all-but-build build

all-but-build: check clean tar spec-copy

.PHONY: tar
tar: rpm-dirs
	cd ${HOME}/rpmbuild; rm -f $(prog)-$(version); ln -s ${srctree} $(prog)-$(version); \
	  tar -X ${CWD}/$(prog).rpm.exclude \
	      -zchf ${HOME}/rpmbuild/SOURCES/$(prog)-$(version).tar.gz $(prog)-$(version)
	rm -f ${HOME}/rpmbuild/$(prog)-$(version)

clean::
	rm -f ${srctree}/file.list

# rpm.conf is need to get the version, so if it is deleted,
# it has to be remade before make can run again, by sourcing
# ./profile.

veryclean: clean
	rm -f ../rpm.conf

.PHONY:
# file.list:
# 	cd ${srctree}; find . -type f ! -name file.list | grep -v -f ${CWD}/$(prog).rpm.exclude > ${srctree}/$@
# 	echo "./file.list" >> ${srctree}/$@

include ${TOP}/rpm/misc-scripts/mk/rpm.mk

# tag the current HEAD on push
# push::
#	tag-it ${prog}
