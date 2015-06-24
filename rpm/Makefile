.PHONY: all
all:
	@echo "Default target does nothing, use all-test to build all RPMs for testing"

SUBDIRS = configtools pbench-agent pbench-report benchmarks tools

.PHONY: all-test
all-test:
	cd ${TOP}/configtools; ${MAKE}
	for i in BUILD BUILDROOT SPECS SOURCES SRPMS RPMS; do rm -rf ${HOME}/rpmbuild/$$i/* ; done
	for i in ${SUBDIRS} ; do ${MAKE} -C $$i all-test ; done

.PHONY: clean
clean:
	cd ${TOP}/configtools; ${MAKE} clean
	for i in BUILD BUILDROOT SPECS SOURCES SRPMS RPMS; do rm -rf ${HOME}/rpmbuild/$$i/* ; done
	for i in ${SUBDIRS} ; do ${MAKE} -C $$i clean ; done
