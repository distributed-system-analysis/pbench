# settings - hardwired, but they could be set from the config file or
# from the command line.
DESTDIR=/opt/pbench-server
OWNER=pbench
GROUP=pbench

# derived directories
BINDIR=${DESTDIR}/bin
LIBDIR=${DESTDIR}/lib

# commands used below
COPY    = cp -a
CHOWN   = chown -R ${OWNER}.${GROUP}
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
	install-bin install-binbase install-bintools install-binscripts \
	install-lib \
	install-server-lib \
	install-makefile \
	install-pbench-scripts \
	install-build-artifacts

install-all: install install-server-lib

install: install-dirs install-bin install-lib install-makefile install-pbench-scripts
	${COPY} VERSION ${DESTDIR}

install-dirs:
	${INSTALL} ${INSTALLOPTS} ${DESTDIR}
	${INSTALL} ${INSTALLOPTS} ${BINDIR}
	${INSTALL} ${INSTALLOPTS} ${LIBDIR}
	${INSTALL} ${INSTALLOPTS} ${LIBDIR}/crontab
	${INSTALL} ${INSTALLOPTS} ${LIBDIR}/pbench

install-bin: install-binbase install-bintools install-binscripts

install-binbase:
	for f in ${binbase} ;do \
	    ${COPY} bin/$$f ${BINDIR} \
	;done

install-bintools:
	for f in ${bintools} ;do \
	    ${COPY} bin/$$f ${BINDIR} \
	;done

install-binscripts:
	cd bin; \
	for f in ${binlinks} ;do \
	    ${COPY} $$f ${BINDIR}; \
	    if [ -e $$f.sh ] ;then \
	        ${COPY} $$f.sh ${BINDIR} \
	    ;elif [ -e $$f.py ] ;then \
	        ${COPY} $$f.py ${BINDIR} \
	    ;fi \
	;done

install-lib:
	${COPY} -r lib ${DESTDIR}

# copy enough to be able to run setup again in the destination directory
install-server-lib:
	${COPY} -r ../lib/pbench/common ../lib/pbench/__init__.py ../lib/pbench/server ../lib/pbench/cli  ${DESTDIR}/lib/pbench
	${COPY} ../lib/pbench.egg-info/PKG-INFO ${DESTDIR}
	for f in ${setupfiles} ;do \
	    ${COPY} ../$$f ${DESTDIR} \
	;done

install-extra: install-setup-files install-build-artifacts

install-setup-files:
	for f in ${setupfiles} ;do \
	    ${COPY} $$f ${DESTDIR} \
	;done

install-makefile:
	${COPY} Makefile ${DESTDIR}

# fix the shebang: rpmbuild does not like unversioned python
install-pbench-scripts:
	if [ -f ../bin/pbench-config ] ;then \
	    sed '1s;.*python$$;#!/usr/bin/env python3;' ../bin/pbench-config > ${DESTDIR}/bin/pbench-config; \
	    sed '1s;.*python$$;#!/usr/bin/env python3;' ../bin/pbench-server > ${DESTDIR}/bin/pbench-server \
	;else \
	    ${COPY} bin/pbench-config ${BINDIR}; \
	    ${COPY} bin/pbench-server ${BINDIR} \
	;fi

# SHA1 and SEQNO - these are used when building an RPM only
# so we provide a target for the spec file to invoke. This
# is *NOT* meant to be invoked interactively.
install-build-artifacts:
	${COPY} SHA1 ${DESTDIR}
	${COPY} SEQNO ${DESTDIR}

clean:
	rm -rf ${DESTDIR}
