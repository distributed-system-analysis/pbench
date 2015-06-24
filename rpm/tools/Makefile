.PHONY: all
all:
	@echo "Default target does nothing, use all-test to build all RPMs for testing"

SUBDIRS = pbench-sysstat pssh

.PHONY: all-test
all-test:
	for i in ${SUBDIRS} ; do ${MAKE} -C $$i all-test ; done

.PHONY: clean
clean:
	for i in ${SUBDIRS} ; do ${MAKE} -C $$i clean ; done
