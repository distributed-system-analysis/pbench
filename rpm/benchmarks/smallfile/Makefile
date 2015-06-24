prog = smallfile
version = $(shell sed -n '/^Version/s/[^:]*:[ 	]*//p' smallfile.spec)
arch = x86_64
url = $(shell sed -n '/^URL/s/[^:]*:[ 	]*//p' smallfile.spec)

all: rpm rpm-copy

rpm: all-but-build build

all-but-build: check clean tar

smallfile:
	git clone ${url}

tar:	smallfile
	rm -f ${prog}-${version}
	ln -s ${prog} ${prog}-${version}
	tar --exclude=.git -zhcf ~/rpmbuild/SOURCES/${prog}-${version}.tar.gz ${prog}-${version}

clean::
	rm -rf ${prog}
	rm -f ${prog}-${version}

include ${TOP}/rpm/misc-scripts/mk/rpm.mk
