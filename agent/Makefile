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
TOOLDIR=${DESTDIR}/tool-scripts
UTILDIR=${DESTDIR}/util-scripts

# commands used below
COPY    = cp -a
CHOWN   = chown -R ${OWNER}.${GROUP}
INSTALL = install
INSTALLOPTS = --directory

# all the scripts that's fit to install
util-scripts = \
	get-internal-tool \
	pbench-add-metalog-option \
	pbench-copy-results \
	pbench-copy-result-tb \
	pbench-display-sysinfo-options \
	pbench-kill-tools \
	pbench-log-timestamp \
	pbench-make-result-tb \
	pbench-move-results \
	pbench-output-monitor \
	pbench-postprocess-tools \
	pbench-register-tool \
	pbench-register-tool-set \
	pbench-send-tools \
	pbench-start-tools \
	pbench-stop-tools \
	pbench-tool-meister-client \
	pbench-tool-meister-start \
	pbench-tool-meister-stop \
	pbench-tool-trigger \
	pbench-verify-sysinfo-options \
	README.md \
	require-rpm \
	tool-meister \
	validate-hostname \
	validate-ipaddress

# Scripts based on the Python Click package, which are generated during
# installation.
click-scripts = \
	pbench-cleanup \
	pbench-clear-results \
	pbench-clear-tools \
	pbench-config \
	pbench-is-local \
	pbench-list-tools \
	pbench-list-triggers \
	pbench-results-move \
	pbench-results-push \
	pbench-register-tool-trigger \
	pbench-tools-kill

bench-scripts = \
	pbench-fio \
	pbench-fio.md \
	pbench-gen-iterations \
	pbench-linpack \
	pbench-specjbb2005 \
	pbench-uperf \
	pbench-uperf.md \
	pbench-user-benchmark \
	templates

bench-postprocess = \
	BenchPostprocess.pm \
	compare-bench-results \
	fio-postprocess \
	fio-postprocess-viz.py \
	fio-prepare-jobfile \
	generate-benchmark-summary \
	linpack-postprocess \
	linpack-postprocess-sample \
	process-iteration-samples \
	uperf-postprocess \
	user-benchmark-wrapper

bench-driver = \
	fio-client \
	linpack \
	linpack-wait

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
	README.md \
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
	jmap-postprocess \
	jstack-postprocess \
	kvm-spinlock-postprocess \
	kvmstat-postprocess \
	kvmtrace-stop-postprocess \
	mpstat-postprocess \
	mpstat-stop-postprocess \
	numastat-postprocess \
	openvswitch-postprocess \
	perf-stop-postprocess \
	pidstat-postprocess \
	proc-interrupts-postprocess \
	proc-sched_debug-postprocess \
	proc-vmstat-postprocess \
	prometheus-metrics-postprocess \
	qemu-migrate-postprocess \
	rabbit-postprocess \
	sar-postprocess \
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

install-destdir:
	${INSTALL} ${INSTALLOPTS} ${DESTDIR}

install-lib:
	${INSTALL} ${INSTALLOPTS} ${LIBDIR}
	${COPY} lib ${DESTDIR}

# NOTE: we deliberately use `/usr/bin/python3` to make sure that when this is
# invoked inside a python virtualenv the pip installation won't uninstall the
# existing pbench module, breaking the environment.
#
# During the Python installation, it's going to test to see if the installation
# directory is on the PYTHONPATH (which it is not...), so put it on the path,
# just for the installation, based on our prefix and the version of Python.
# For some reason, this only seems to be a problem on RHEL platforms prior to 9.
pver = $(shell /usr/bin/python3 -c 'import sys; print(f"python{sys.version_info.major}.{sys.version_info.minor}")')
install-python3-setup: install-util-scripts install-lib
	${COPY} requirements.txt ${DESTDIR}
	mkdir -p ${DESTDIR}/python3
	cd .. && PYTHONPATH=${DESTDIR}/python3/lib/${pver}/site-packages \
	  /usr/bin/python3 -m pip install --prefix=${DESTDIR}/python3 -e .
	${COPY} $(addprefix ${DESTDIR}/python3/bin/, ${click-scripts}) ${UTILDIR}/
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
	${INSTALL} ${INSTALLOPTS} ${BENCHDIR}/driver
	cd bench-scripts/driver; \
	    ${COPY} ${bench-driver} ${BENCHDIR}/driver
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

clean:
	rm -rf ${DESTDIR}
