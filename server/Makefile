# DESTDIR *must* be overwritten from the command line
DESTDIR=/dev/null

# settings - hardwired, but they could be set from the config file or
# from the command line.
OWNER=pbench
GROUP=pbench

# derived directories
BINDIR=${DESTDIR}/bin
LIBDIR=${DESTDIR}/lib

# commands used below
COPY    = cp -a
RM      = rm
CHOWN   = chown -R ${OWNER}.${GROUP}
LINK	= ln -s
INSTALL = install
#INSTALLOPTS = --mode 755 --directory --owner=${OWNER} --group=${GROUP}
INSTALLOPTS = --directory

# targets
.PHONY: install \
	install-dirs \
	install-bin \
	install-lib \
	install-server-lib \

install: install-dirs install-python3-setup
	${COPY} VERSION ${DESTDIR}

install-dirs:
	${INSTALL} ${INSTALLOPTS} ${DESTDIR}
	${INSTALL} ${INSTALLOPTS} ${BINDIR}
	${INSTALL} ${INSTALLOPTS} ${LIBDIR}
	${INSTALL} ${INSTALLOPTS} ${LIBDIR}/crontab
	${INSTALL} ${INSTALLOPTS} ${LIBDIR}/pbench
	${INSTALL} ${INSTALLOPTS} ${LIBDIR}/pbench/cli

install-python3-setup: install-bin install-lib
	mkdir -p ${DESTDIR}/python3
	${COPY} ../requirements.txt ${DESTDIR}
	(cd ..; SKIP_GENERATE_AUTHORS=1 SKIP_WRITE_GIT_CHANGELOG=1 python3 setup.py install --prefix=${DESTDIR}/python3)
	${COPY} ${DESTDIR}/python3/bin/pbench-config ${DESTDIR}/python3/bin/pbench-server ${BINDIR}/
	${RM} -r ${DESTDIR}/python3
	${COPY} ../lib/pbench ${LIBDIR}/
	${RM} -r $$(find ${LIBDIR} -name __pycache__) ${LIBDIR}/pbench/test ${LIBDIR}/pbench/agent ${LIBDIR}/pbench/cli/agent

install-bin:
	${COPY} bin/pbench-* ${BINDIR}/
	for i in pbench-server-activate pbench-server-activate-create-results-dir-structure pbench-server-activate-setup-results-host-info pbench-server-activate-setup-web-server pbench-server-activate-start-httpd pbench-server-config-activate ;do rm ${BINDIR}/$${i} ;done

install-lib:
	${COPY} lib ${DESTDIR}
	${RM} ${DESTDIR}/lib/config/nginx.conf.example

clean:
	${RM} -rf ${DESTDIR}
