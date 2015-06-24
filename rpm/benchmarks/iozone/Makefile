prog = iozone
# need to update Source0 in the spec file if this is changed
version = 3.430
iozversion = $(shell echo ${version} | sed 's/\./_/')
arch = x86_64

all: rpm rpm-copy

rpm: all-but-build build

all-but-build: check clean iozone-tar

# iozone uses a peculiar naming scheme, so we can't use spectool
iozname=${prog}${iozversion}
SRCURL = $(shell dirname $$(grep Source0 ${prog}.spec | awk '{print $$2;}'))/${iozname}.tar

.PHONY: srcurl
srcurl:
	@echo "iozone source URL: ${SRCURL}"

iozone-tar:
	cd ${HOME}/rpmbuild/SOURCES;\
	wget ${SRCURL};\
	tar xf ${iozname}.tar;\
	mv ${iozname} ${prog}-${version};\
	tar cf ${prog}-${version}.tar ${prog}-${version};\
	rm -rf ${prog}-${version}

include ${TOP}/rpm/misc-scripts/mk/rpm.mk
