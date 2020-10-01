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
	 getconf.py \
	 pbench-add-metalog-option \
	 pbench-agent-config-activate \
	 pbench-agent-config-ssh-key \
	 pbench-avg-stddev \
	 pbench-cleanup \
	 pbench-clear-results \
	 pbench-clear-tools \
	 pbench-collect-sysinfo \
	 pbench-copy-results \
	 pbench-copy-result-tb \
	 pbench-get-metric-data \
	 pbench-get-primary-metric \
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
	postprocess \
	templates


tool-scripts = \

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
	${INSTALL} ${INSTALLOPTS} ${LIBDIR}/configtools
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
	${COPY} -r ${bench-scripts} ${BENCHDIR}
	cd ${BENCHDIR}; \
	ln -sf postprocess/compare-bench-results compare-bench-results

# install-bench-script-postprocess:
# 	cd bench-scripts; \
# 	${COPY} -r postprocess ${BENCHDIR}

install-tool-scripts:
	${COPY} -r tool-scripts ${DESTDIR}

install-stockpile:
	${COPY} -r stockpile ${DESTDIR}

install-lib:
	${COPY} -r lib ${DESTDIR}

install-configtools:
	${COPY} -r ../lib/configtools ${DESTDIR}/lib

# SHA1 and SEQNO - these are used when building an RPM only
# so we provide a target for the spec file to invoke. This
# is *NOT* meant to be invoked interactively.
install-build-artifacts:
	${COPY} ../SHA1 ${DESTDIR}
	${COPY} ../SEQNO ${DESTDIR}
	${COPY} ../MANIFEST ${DESTDIR}

clean:
	rm -rf ${DESTDIR}
