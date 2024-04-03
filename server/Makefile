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

click-scripts = \
	pbench-audit \
	pbench-reindex \
	pbench-report-generator \
	pbench-tree-manage \
	pbench-user-create \
	pbench-user-update \
	pbench-user-list \
	pbench-user-delete

# targets
.PHONY: install \
	install-dirs \
	install-bin \
	install-lib \
	install-server-lib

install: install-dirs install-python3-setup
	${COPY} VERSION ${DESTDIR}

install-dirs:
	${INSTALL} ${INSTALLOPTS} ${DESTDIR}
	${INSTALL} ${INSTALLOPTS} ${BINDIR}
	${INSTALL} ${INSTALLOPTS} ${LIBDIR}
	${INSTALL} ${INSTALLOPTS} ${LIBDIR}/pbench
	${INSTALL} ${INSTALLOPTS} ${LIBDIR}/pbench/cli

# NOTE: we deliberately use `/usr/bin/python3` to make sure that when this is
# invoked inside a python virtualenv the pip installation won't uninstall the
# existing pbench module, breaking the environment.
install-python3-setup: install-bin install-lib
	mkdir -p ${DESTDIR}/python3
	${COPY} requirements.txt ${DESTDIR}
	(cd ..; /usr/bin/python3 -m pip install --prefix=${DESTDIR}/python3 -e .)
	${COPY} $(addprefix ${DESTDIR}/python3/bin/, pbench-server-config pbench-server ${click-scripts}) ${BINDIR}/
	${RM} -r ${DESTDIR}/python3
	${COPY} ../lib/pbench ${LIBDIR}/
	${RM} -r $$(find ${LIBDIR} -name __pycache__) ${LIBDIR}/pbench/test ${LIBDIR}/pbench/agent ${LIBDIR}/pbench/cli/agent

install-bin:
	${COPY} bin/pbench-* ${BINDIR}/

install-lib:
	${COPY} lib ${DESTDIR}

clean:
	${RM} -rf ${DESTDIR}
