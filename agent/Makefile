# Caller should override `DESTDIR` when invoking make
DESTDIR=/dev/null
# settings - hardwired, but they could be set from the config file or
# from the command line.
OWNER=pbench
GROUP=pbench

# derived directories
ANSIBLEDIR=${DESTDIR}/ansible
BENCHDIR=${DESTDIR}/bench-scripts
CONFIGDIR=${DESTDIR}/config
LIBDIR=${DESTDIR}/lib
STOCKPILEDIR=${DESTDIR}/stockpile
TOOLDIR=${DESTDIR}/tool-scripts
UTILDIR=${DESTDIR}/util-scripts

# commands used below
COPY    = cp -a
CHOWN   = chown -R ${OWNER}.${GROUP}
INSTALL = install
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
	pbench-collect-sysinfo \
	pbench-copy-results \
	pbench-copy-result-tb \
	pbench-end-tools \
	pbench-get-iteration-metrics \
	pbench-get-metric-data \
	pbench-get-primary-metric \
	pbench-import-cdm \
	pbench-init-tools \
	pbench-kill-tools \
	pbench-list-tools \
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
	pbench-send-tools \
	pbench-start-tools \
	pbench-stop-tools \
	pbench-sysinfo-dump \
	pbench-tool-meister-client \
	pbench-tool-meister-start \
	pbench-tool-meister-stop \
	pbench-tool-trigger \
	README \
	require-rpm \
	tool-meister

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
	dcgm \
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
	meta.json \
	mpstat \
	node-exporter \
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
	install-destdir \
	install-util-scripts \
	install-bench-scripts \
	install-tool-scripts \
	install-ansible

# SHA1 and SEQNO - these are used when building an RPM only
# so we provide a target for the spec file to invoke. This
# is *NOT* meant to be invoked interactively.
install: install-destdir install-python3-setup install-bench-scripts install-tool-scripts install-ansible
	${COPY} VERSION ${DESTDIR}
	${COPY} base ${DESTDIR}
	${COPY} profile ${DESTDIR}
	${INSTALL} ${INSTALLOPTS} ${CONFIGDIR}
	${INSTALL} ${INSTALLOPTS} ${CONFIGDIR}/benchmark
	${COPY} config ${DESTDIR}
	${COPY} templates ${DESTDIR}
	${INSTALL} ${INSTALLOPTS} ${STOCKPILEDIR}
	${COPY} stockpile ${DESTDIR}

install-destdir:
	${INSTALL} ${INSTALLOPTS} ${DESTDIR}

install-lib:
	${INSTALL} ${INSTALLOPTS} ${LIBDIR}
	${COPY} lib ${DESTDIR}

install-python3-setup: install-util-scripts install-lib
	${COPY} requirements.txt ${DESTDIR}
	mkdir -p ${DESTDIR}/python3
	(cd ..; SKIP_GENERATE_AUTHORS=1 SKIP_WRITE_GIT_CHANGELOG=1 python3 setup.py install --prefix=${DESTDIR}/python3)
	${COPY} ${DESTDIR}/python3/bin/pbench-config ${UTILDIR}/
	${COPY} ${DESTDIR}/python3/bin/pbench-clear-tools ${UTILDIR}/
	${COPY} ${DESTDIR}/python3/bin/pbench-list-triggers ${UTILDIR}/
	rm -rf ${DESTDIR}/python3
	${COPY} ../lib/pbench ${LIBDIR}/
	rm -r $$(find ${LIBDIR} -name __pycache__) ${LIBDIR}/pbench/test ${LIBDIR}/pbench/server ${LIBDIR}/pbench/cli/server

install-util-scripts: install-destdir
	${INSTALL} ${INSTALLOPTS} ${UTILDIR}
	cd util-scripts; \
	${COPY} ${util-scripts} ${UTILDIR}

install-bench-scripts: install-destdir
	${INSTALL} ${INSTALLOPTS} ${BENCHDIR}
	${INSTALL} ${INSTALLOPTS} ${BENCHDIR}/templates
	cd bench-scripts; \
	${COPY} ${bench-scripts} ${BENCHDIR}
	${INSTALL} ${INSTALLOPTS} ${BENCHDIR}/postprocess
	cd bench-scripts/postprocess; \
	${COPY} ${bench-postprocess} ${BENCHDIR}/postprocess
	cd ${BENCHDIR}; \
	ln -sf postprocess/compare-bench-results compare-bench-results

install-tool-scripts: install-destdir
	${INSTALL} ${INSTALLOPTS} ${TOOLDIR}
	cd tool-scripts; \
	${COPY} ${tool-scripts} ${TOOLDIR}
	${INSTALL} ${INSTALLOPTS} ${TOOLDIR}/datalog
	cd tool-scripts/datalog; \
	${COPY} ${tool-datalogs} ${TOOLDIR}/datalog
	${INSTALL} ${INSTALLOPTS} ${TOOLDIR}/postprocess
	cd tool-scripts/postprocess; \
	${COPY} ${tool-postprocess} ${TOOLDIR}/postprocess

install-ansible: install-destdir
	${INSTALL} ${INSTALLOPTS} ${ANSIBLEDIR}
	cd ansible; \
	${COPY} ara ${ANSIBLEDIR}

clean:
	rm -rf ${DESTDIR}
