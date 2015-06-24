prog = dbench
version = 4.00
arch = x86_64

all: rpm rpm-copy

rpm: all-but-build build

all-but-build: check clean tar copy-patches

dbench:
	git clone git://git.samba.org/sahlberg/dbench.git dbench

tar:	dbench
	rm -f ${prog}-${version}
	ln -s ${prog} ${prog}-${version}
	cd ${prog}; rm -f configure Makefile config.h
	mkdir -p ~/rpmbuild/SOURCES
	tar zhcf ~/rpmbuild/SOURCES/${prog}-${version}.tar.gz ${prog}-${version}

copy-patches:
	cp dbench.patch ~/rpmbuild/SOURCES

include ${TOP}/rpm/misc-scripts/mk/rpm.mk

clean::
	rm -rf ${prog}
	rm -f ${prog}-${version}
