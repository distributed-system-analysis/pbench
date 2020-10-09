# settings - hardwired, but they could be set from the config file.
DESTDIR=/opt/pbench-web-server

OWNER=pbench
GROUP=pbench

# commands used below
COPY    = cp -a
CHOWN   = chown -R ${OWNER}.${GROUP}
INSTALL = install
# The following requires root, so we avoid it here: it causes problems when building an RPM.
# Instead, we'll take care of it when the RPM is installed.
# For manual installation, we might resort to a conditional.
#INSTALLOPTS = --mode 755 --directory --owner=${OWNER} --group=${GROUP}
INSTALLOPTS = --directory

# targets
.PHONY: install \
	install-dirs \
	install-v0.2 \
	install-v0.3 \
	install-makefile \
	clean

install: install-dirs install-v0.2 install-v0.3
	${COPY} package.json ${DESTDIR}
	${COPY} VERSION ${DESTDIR}

install-dirs:
	${INSTALL} ${INSTALLOPTS} ${DESTDIR}
	${INSTALL} ${INSTALLOPTS} ${DESTDIR}/css
	${INSTALL} ${INSTALLOPTS} ${DESTDIR}/css/v0.2
	${INSTALL} ${INSTALLOPTS} ${DESTDIR}/css/v0.3
	${INSTALL} ${INSTALLOPTS} ${DESTDIR}/js
	${INSTALL} ${INSTALLOPTS} ${DESTDIR}/js/v0.2
	${INSTALL} ${INSTALLOPTS} ${DESTDIR}/js/v0.3

install-v0.2:
	${COPY} v0.2/css/* ${DESTDIR}/css/v0.2
	${COPY} v0.2/js/* ${DESTDIR}/js/v0.2

install-v0.3:
	${COPY} v0.3/LICENSE.TXT ${DESTDIR}/css/v0.3
	${COPY} v0.3/LICENSE.TXT ${DESTDIR}/js/v0.3
	${COPY} v0.3/css/* ${DESTDIR}/css/v0.3
	${COPY} v0.3/js/* ${DESTDIR}/js/v0.3

# This is used by the spec file: it just copies the installed structure over without
# any modifications.
clone:
	${INSTALL} ${INSTALLOPTS} ${DESTDIR}
	${COPY} -r . ${DESTDIR}

clean:
	rm -rf ${DESTDIR}
