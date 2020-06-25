# -*- mode: makefile -*-
.PHONY: check
check:
	if [ "${version}" == "" ] ;then echo "version undefined" > /dev/stderr; exit 1 ;fi
	if [ "${prog}" == "" ] ;then echo "prog undefined" > /dev/stderr ; exit 2 ;fi

RPMDIRS = BUILD BUILDROOT SPECS SOURCES SRPMS RPMS

.PHONY: rpm-dirs
rpm-dirs:
	for i in ${RPMDIRS}; do mkdir -p ${HOME}/rpmbuild/$$i ; done

.PHONY: rpm-clean
rpm-clean:
	for i in ${RPMDIRS}; do rm -rf ${HOME}/rpmbuild/$$i/* ; done

###########################################################################
# these are used in the Makefiles that include this file
RPMSRC = ${HOME}/rpmbuild/SOURCES
RPMSRPM = ${HOME}/rpmbuild/SRPMS
RPMSPEC = ${HOME}/rpmbuild/SPECS

###########################################################################

# building on COPR.
# version and sha1 have to be provided by the including Makefile.
# The including Makefile also has to provide the srpm target.

.SECONDEXPANSION:
$(RPMSRPM)/$(prog)-$(version)-$(seqno)$(sha1).src.rpm: srpm

ifdef COPR_USER
_copr_user = ${COPR_USER}
else
_copr_user = ${USER}
endif

copr\
copr-test \
copr-interim \
copr-index \
copr-inotify \
copr-dashboard:	$(RPMSRPM)/$(prog)-$(version)-$(seqno)$(sha1).src.rpm
	copr-cli build $(_copr_user)/$(subst copr,pbench,$@) $(RPMSRPM)/$(prog)-$(VERSION)-$(seqno)g$(sha1).src.rpm

veryclean:: clean rpm-clean
