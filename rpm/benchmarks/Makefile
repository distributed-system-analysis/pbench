.PHONY: all
all:
	@echo "Default target does nothing, use all-test to build all RPMs for testing"

SUBDIRS = dbench fio iozone iperf linpack netperf smallfile stress sysbench uperf

.PHONY: all-test
all-test:
	for i in ${SUBDIRS} ; do ${MAKE} -C $$i all-test ; done

.PHONY: clean
clean:
	for i in ${SUBDIRS} ; do ${MAKE} -C $$i clean ; done
