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
CHOWN   = chown -R ${OWNER}.${GROUP}
LINK	= ln -s
INSTALL = install
#INSTALLOPTS = --mode 755 --directory --owner=${OWNER} --group=${GROUP}
INSTALLOPTS = --directory

# all the scripts that's fit to install
binbase = \
	pbench-base.py\
	pbench-base.sh

# pbench-server-activate-create-crontab is needed by the ansible installation playbook.
# pbench-remote*, pbench-satelliter-state-change.py and pbench-server-set-result-state
# are needed on satellites, but we install them everywhere.
bintools = \
	pbench-trampoline\
	pbench-pp-status\
	pbench-server-activate-create-crontab\
	pbench-remote-satellite-state-change\
	pbench-remote-sync-package-tarballs\
	pbench-satellite-state-change.py\
	pbench-server-set-result-state

# All of these should be linked to pbench-trampoline.
# In addition, each one has a companion (either .sh or .py)
# which needs to be installed as well.
binlinks = \
	pbench-audit-server\
	pbench-backup-tarballs\
	pbench-check-tb-age\
	pbench-clean-up-dangling-results-links\
	pbench-copy-sosreports\
	pbench-cull-unpacked-tarballs\
	pbench-dispatch\
	pbench-index\
	pbench-reindex\
	pbench-report-status\
	pbench-satellite-cleanup\
	pbench-satellite-state-change\
	pbench-server-prep-shim-002\
	pbench-sync-package-tarballs\
	pbench-sync-satellite\
	pbench-unpack-tarballs\
	pbench-verify-backup-tarballs\

setupfiles = \
	setup.py \
	setup.cfg \
	requirements.txt \
	README.md

# targets
.PHONY: install \
	install-dirs \
	install-bin install-binbase install-bintools install-binlinks \
	install-lib \
	install-server-lib \
	install-pbench-scripts \
	install-build-artifacts

install-all: install install-server-lib

install: install-dirs install-bin install-lib install-pbench-scripts
	${COPY} VERSION ${DESTDIR}

install-dirs:
	${INSTALL} ${INSTALLOPTS} ${DESTDIR}
	${INSTALL} ${INSTALLOPTS} ${BINDIR}
	${INSTALL} ${INSTALLOPTS} ${LIBDIR}
	${INSTALL} ${INSTALLOPTS} ${LIBDIR}/crontab
	${INSTALL} ${INSTALLOPTS} ${LIBDIR}/pbench
	${INSTALL} ${INSTALLOPTS} ${LIBDIR}/pbench/cli

install-bin: \
	install-binbase \
	install-bintools \
	install-binlinks

install-binbase:
	for f in ${binbase} ;do \
	    ${COPY} bin/$$f ${BINDIR} \
	;done

install-bintools:
	for f in ${bintools} ;do \
	    ${COPY} bin/$$f ${BINDIR} \
	;done

install-binlinks:
	for f in ${binlinks} ;do \
	    ${LINK} pbench-trampoline ${BINDIR}/$$f \
	    ;if [ -f bin/$$f.py ] ;then \
		${COPY} bin/$$f.py ${BINDIR} \
	    ;elif [ -f bin/$$f.sh ] ;then \
		${COPY} bin/$$f.sh ${BINDIR}\
	    ;else \
		exit 1\
	    ;fi \
	;done

install-lib:
	${COPY} -r lib ${DESTDIR}
	${RM} ${DESTDIR}/lib/config/nginx.conf.example

# copy only the server-related bits
install-server-lib:
	${COPY} -r ../lib/pbench/common ../lib/pbench/__init__.py ../lib/pbench/server ${DESTDIR}/lib/pbench
	${COPY} -r ../lib/pbench/cli/getconf.py ../lib/pbench/cli/__init__.py ../lib/pbench/cli/server ${DESTDIR}/lib/pbench/cli
	for f in ${setupfiles} ;do \
	    ${COPY} ../$$f ${DESTDIR} \
	;done

install-extra: install-setup-files install-build-artifacts

install-setup-files:
	for f in ${setupfiles} ;do \
	    ${COPY} $$f ${DESTDIR} \
	;done

# fix the shebang: rpmbuild does not like unversioned python
install-pbench-scripts:
	if [ -f ${DESTDIR}/../bin/pbench-config ] ;then \
	    sed '1s;.*python$$;#!/usr/bin/env python3;' ${DESTDIR}/../bin/pbench-config > ${DESTDIR}/bin/pbench-config; \
	    sed '1s;.*python$$;#!/usr/bin/env python3;' ${DESTDIR}/../bin/pbench-server > ${DESTDIR}/bin/pbench-server \
	;else \
	    ${COPY} ${DESTDIR}/../bin/pbench-config ${BINDIR}; \
	    ${COPY} ${DESTDIR}/../bin/pbench-server ${BINDIR} \
	;fi

# SHA1 and SEQNO - these are used when building an RPM only
# so we provide a target for the spec file to invoke. This
# is *NOT* meant to be invoked interactively.
install-build-artifacts:
	${COPY} SHA1 ${DESTDIR}
	${COPY} SEQNO ${DESTDIR}

clean:
	rm -rf ${DESTDIR}
