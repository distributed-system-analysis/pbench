all: build build/bin/getconf.py build/bin/gethosts.py build/MANIFEST build/profile build/setup.py

build/setup.py: setup.py
	cp setup.py build/

build/MANIFEST: MANIFEST
	cp MANIFEST build/

build/profile: profile
	cp profile build/

build/bin/getconf.py: build/bin/getconf.2.py build/bin/getconf.3.py
	(cd build/bin; ln -sf getconf.2.py getconf.py)

build/bin/gethosts.py: build/bin/gethosts.2.py build/bin/gethosts.3.py
	(cd build/bin; ln -sf gethosts.2.py gethosts.py)

build/bin/getconf.2.py: bin/getconf.2.py
	mkdir -p build/bin
	cp bin/getconf.2.py build/bin/

build/bin/gethosts.2.py: bin/gethosts.2.py
	mkdir -p build/bin
	cp bin/gethosts.2.py build/bin/

build/bin/getconf.3.py: bin/getconf.2.py
	sed '1s/$$/3/' bin/getconf.2.py > $@
	chmod ugo+x $@

build/bin/gethosts.3.py: bin/gethosts.2.py
	sed '1s/$$/3/' bin/gethosts.2.py > $@
	chmod ugo+x $@

build/configtools/__init__.py: configtools/__init__.py
	mkdir -p build/configtools
	cp configtools/__init__.py build/configtools/

prep-for-rpm: build/bin/getconf.2.py build/bin/gethosts.2.py build/profile build/MANIFEST build/setup.py build/configtools/__init__.py

build: setup.py configtools/__init__.py
	python setup.py build

install: build
	python setup.py --skip-build install

clean:
	rm -f  configtools/__init__.pyc
	rm -rf build
