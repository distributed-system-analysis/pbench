# settings - hardwired, but they could be set from the config file or
# from the command line.
DESTDIR=/opt/pbench-agent-test
OWNER=pbench
GROUP=pbench

# derived directories
CONFIGDIR=${DESTDIR}/config
UTILDIR=${DESTDIR}/util-scripts
BENCHDIR=${DESTDIR}/bench-scripts
TOOLDIR=${DESTDIR}/tool-scripts
LIBDIR=${DESTDIR}/lib

# commands used below
COPY    = cp -a
CHOWN   = chown -R ${OWNER}.${GROUP}
INSTALL = install
#INSTALLOPTS = --mode 755 --directory --owner=${OWNER} --group=${GROUP}
INSTALLOPTS = --directory

# all the scripts that's fit to install
util-scripts = \
	cdm-get-iterations \
	pbench-add-metalog-option \
	pbench-agent-config-activate \
	pbench-agent-config-ssh-key \
	pbench-avg-stddev \
	pbench-cleanup \
	pbench-clear-results \
	pbench-clear-tools \
	pbench-collect-sysinfo \
	pbench-config \
	pbench-copy-results \
	pbench-copy-result-tb \
	pbench-get-iteration-metrics \
	pbench-get-metric-data \
	pbench-get-primary-metric \
	pbench-import-cdm \
	pbench-kill-tools \
	pbench-list-tools \
	pbench-list-triggers \
	pbench-log-timestamp \
	pbench-make-result-tb \
	pbench-metadata-log \
	pbench-move-results \
	pbench-output-monitor \
	pbench-postprocess-tools \
	pbench-postprocess-tools-cdm \
	pbench-register-tool \
	pbench-register-tool-set \
	pbench-register-tool-trigger \
	pbench-remote-sysinfo-dump \
	pbench-start-tools \
	pbench-stop-tools \
	pbench-sysinfo-dump \
	pbench-tool-trigger \
	README \
	require-rpm

bench-scripts = \
	pbench-cyclictest \
	pbench-dbench \
	pbench-fio \
	pbench-fio.md \
	pbench-gen-iterations \
	pbench-iozone \
	pbench-linpack \
	pbench-migrate \
	pbench-netperf \
	pbench-run-benchmark \
	pbench-run-benchmark-sample \
	pbench-specjbb2005 \
	pbench-trafficgen \
	pbench-uperf \
	pbench-uperf.md \
	pbench-user-benchmark \
	templates

bench-postprocess = \
	BenchPostprocess.pm \
	compare-bench-results \
	dbench-postprocess \
	fio-postprocess \
	fio-postprocess-cdm \
	fio-postprocess-viz.py \
	fio-prepare-jobfile \
	generate-benchmark-summary \
	linpack-postprocess \
	linpack-postprocess-cdm \
	linpack-prepare-input-file \
	process-iteration-samples \
	trafficgen-postprocess \
	trafficgen-postprocess-cdm \
	uperf-postprocess \
	user-benchmark-wrapper

tool-scripts = \
	base-tool \
	blktrace \
	bpftrace \
	cpuacct \
	disk \
	dm-cache \
	docker \
	docker-info \
	external-data-source \
	haproxy-ocp \
	iostat \
	jmap \
	jstack \
	kvm-spinlock \
	kvmstat \
	kvmtrace \
	lockstat \
	mpstat \
	numastat \
	oc \
	openvswitch \
	pcp \
	perf \
	perf.README \
	pidstat \
	pprof \
	proc-interrupts \
	proc-sched_debug \
	proc-vmstat \
	prometheus-metrics \
	qemu-migrate \
	rabbit \
	README \
	sar \
	strace \
	sysfs \
	systemtap \
	tcpdump \
	turbostat \
	user-tool \
	virsh-migrate \
	vmstat

tool-datalogs = \
	blktrace-datalog \
	bpftrace-datalog \
	cpuacct-datalog \
	disk-datalog \
	dm-cache-datalog \
	docker-datalog \
	docker-info-datalog \
	File-Capture-datalog \
	haproxy-ocp-datalog \
	iostat-datalog \
	jmap-datalog \
	jstack-datalog \
	kvm-spinlock-datalog \
	kvmstat-datalog \
	kvmtrace-datalog \
	lockstat-datalog \
	mpstat-datalog \
	numastat-datalog \
	oc-datalog \
	openvswitch-datalog \
	pcp-datalog \
	perf-datalog \
	pidstat-convert \
	pidstat-datalog \
	pprof-datalog \
	prometheus-metrics-datalog \
	qemu-migrate-datalog \
	rabbit-datalog \
	sar-datalog \
	strace-datalog \
	sysfs-datalog \
	systemtap-datalog \
	tcpdump-datalog \
	turbostat-datalog \
	virsh-migrate-datalog \
	vmstat-datalog

tool-postprocess = \
	blktrace-stop-postprocess \
	cpuacct-postprocess \
	cpuacct-stop-postprocess \
	disk-postprocess \
	docker-postprocess \
	haproxy-ocp-postprocess \
	iostat-postprocess \
	iostat-postprocess-cdm \
	jmap-postprocess \
	jstack-postprocess \
	kvm-spinlock-postprocess \
	kvmstat-postprocess \
	kvmtrace-stop-postprocess \
	mpstat-postprocess \
	mpstat-postprocess-cdm \
	mpstat-stop-postprocess \
	numastat-postprocess \
	openvswitch-postprocess \
	pcp-postprocess \
	perf-stop-postprocess \
	pidstat-postprocess \
	pidstat-postprocess-cdm \
	proc-interrupts-postprocess \
	proc-sched_debug-postprocess \
	proc-vmstat-postprocess \
	prometheus-metrics-postprocess \
	qemu-migrate-postprocess \
	rabbit-postprocess \
	sar-postprocess \
	sar-postprocess-cdm \
	sysfs-postprocess \
	virsh-migrate-postprocess \
	vmstat-postprocess

# targets
.PHONY: install \
	install-dirs \
	install-ansible \
	install-util-scripts \
	install-bench-scripts \
	install-tool-scripts \
	install-lib \
	install-configtools \
	install-stockpile \
	install-build-artifacts

install: install-dirs install-ansible install-config install-util-scripts install-bench-scripts install-tool-scripts install-lib install-configtools install-stockpile
	${COPY} VERSION ${DESTDIR}
	${COPY} Makefile ${DESTDIR}
	${COPY} base ${DESTDIR}
	${COPY} profile ${DESTDIR}

install-dirs:
	${INSTALL} ${INSTALLOPTS} ${DESTDIR}
	${INSTALL} ${INSTALLOPTS} ${DESTDIR}/ansible
	${INSTALL} ${INSTALLOPTS} ${CONFIGDIR}
	${INSTALL} ${INSTALLOPTS} ${CONFIGDIR}/benchmark
	${INSTALL} ${INSTALLOPTS} ${UTILDIR}
	${INSTALL} ${INSTALLOPTS} ${BENCHDIR}
	${INSTALL} ${INSTALLOPTS} ${BENCHDIR}/postprocess
	${INSTALL} ${INSTALLOPTS} ${BENCHDIR}/templates
	${INSTALL} ${INSTALLOPTS} ${TOOLDIR}
	${INSTALL} ${INSTALLOPTS} ${TOOLDIR}/postprocess
	${INSTALL} ${INSTALLOPTS} ${TOOLDIR}/datalog
	${INSTALL} ${INSTALLOPTS} ${LIBDIR}
	${INSTALL} ${INSTALLOPTS} ${DESTDIR}/stockpile

install-ansible:
	${COPY} -r ansible ${DESTDIR}

install-config:
	${COPY} -r config ${DESTDIR}

install-util-scripts:
	cd util-scripts; \
	${COPY} ${util-scripts} ${UTILDIR}

install-bench-scripts:
	cd bench-scripts; \
	${COPY} ${bench-scripts} ${BENCHDIR}
	cd bench-scripts/postprocess; \
	${COPY} ${bench-postprocess} ${BENCHDIR}/postprocess
	cd ${BENCHDIR}; \
	ln -sf postprocess/compare-bench-results compare-bench-results

# install-bench-script-postprocess:
# 	cd bench-scripts; \
# 	${COPY} -r postprocess ${BENCHDIR}

install-tool-scripts:
	cd tool-scripts; \
	${COPY} ${tool-scripts} ${TOOLDIR}
	cd tool-scripts/datalog; \
	${COPY} ${tool-datalogs} ${TOOLDIR}/datalog
	cd tool-scripts/postprocess; \
	${COPY} ${tool-postprocess} ${TOOLDIR}/postprocess

install-stockpile:
	${COPY} -r stockpile ${DESTDIR}

install-lib:
	${COPY} -r lib ${DESTDIR}

# Yuck!
install-configtools:
	if [ ! -d lib/pbench ] ;then ${COPY} -r ../lib/pbench ${LIBDIR} ;fi

# SHA1 and SEQNO - these are used when building an RPM only
# so we provide a target for the spec file to invoke. This
# is *NOT* meant to be invoked interactively.
install-build-artifacts:
	${COPY} SHA1 ${DESTDIR}
	${COPY} SEQNO ${DESTDIR}

clean:
	rm -rf ${DESTDIR}
