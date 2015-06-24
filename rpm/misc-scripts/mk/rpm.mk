# -*- mode: makefile -*-
REMOTETARBALL = $(shell grep '^Source0' ${prog}.spec | sed 's/[^:]*: *//')

.PHONY: check
check:
	if [ "${version}" == "" ] ;then echo "version undefined" > /dev/stderr; exit 1 ;fi
	if [ "${prog}" == "" ] ;then echo "prog undefined" > /dev/stderr ; exit 2 ;fi

.PHONY: rpm-dirs
rpm-dirs:
	for i in BUILD BUILDROOT SPECS SOURCES SRPMS RPMS; do mkdir -p ${HOME}/rpmbuild/$$i ; done

.PHONY: rpm-clean
rpm-clean:
	for i in BUILD BUILDROOT SPECS SOURCES SRPMS RPMS; do rm -rf ${HOME}/rpmbuild/$$i/* ; done

dot-clean:
	rm -f .rpm-copy .spec-copy

# Provide a rule for this one in individual Makefiles
localtar:: rpm-dirs

# sometimes this can be used - it's not a general purpose target,
# so maybe kick it out of here?
# remotetar:
# 	cd ~/rpmbuild/SOURCES; wget ${REMOTETARBALL}
remotetar: spec-copy
	cd ~/rpmbuild/SOURCES; spectool -g ../SPECS/${prog}.spec

# most builds use this target with an empty USE_GIT_SHA1 - only pbench and
# pbench-report call it with a non-empty USE_GIT_SHA1
.PHONY: spec-copy
spec-copy: .spec-copy
.spec-copy:
	set-version-release ${version} $(prog).spec ${USE_GIT_SHA1} > ${HOME}/rpmbuild/SPECS/${prog}.spec && touch .spec-copy

MOCKS = $(shell PYTHONPATH=${TOP}/configtools/build/lib:$$PYTHONPATH PATH=${TOP}/configtools/build/bin:$$PATH getconf.py -l mocks ${prog} repo)

# backgrounding the mock builds saves a bit of time: 1m 50s vs 2m 15s
# but it's still too long
.PHONY: build
build: .build
.build: .spec-copy
	rm -f ${HOME}/rpmbuild/SRPMS/$(prog)-*.src.rpm
	rpmbuild -bs ${HOME}/rpmbuild/SPECS/$(prog).spec
	echo "mock output in ./mock-build.log"
	for c in ${MOCKS} ;do\
	    mock -r $${c} ${HOME}/rpmbuild/SRPMS/$(prog)-*.src.rpm & \
	done  > ./mock-build.log 2>&1; wait && touch .build

.PHONY: clean-build
clean-build:
	rm -f .build mock-build.log

# for sanity checking
build-local:
	rpmbuild -bb ${HOME}/rpmbuild/SPECS/$(prog).spec

# At this point, we have ${prog}-${version}-${release}.${distro}.${arch}.rpm
# in /var/lib/mock/${mock_env}/result.
.PHONY: rpm-copy
rpm-copy: .rpm-copy
.rpm-copy: .build
	for c in ${MOCKS} ;do\
	    mock-copy ${prog} $${c} ~/rpmbuild/RPMS ${arch}\
	;done && touch .rpm-copy

repohost    = $(shell PYTHONPATH=${TOP}/configtools/build/lib:$$PYTHONPATH PATH=${TOP}/configtools/build/bin:$$PATH getconf.py repohost $(prog) repo)
repouser    = $(shell PYTHONPATH=${TOP}/configtools/build/lib:$$PYTHONPATH PATH=${TOP}/configtools/build/bin:$$PATH getconf.py repouser $(prog) repo)
repodir     = $(shell PYTHONPATH=${TOP}/configtools/build/lib:$$PYTHONPATH PATH=${TOP}/configtools/build/bin:$$PATH getconf.py repodir $(prog) repo)
testrepodir = $(shell PYTHONPATH=${TOP}/configtools/build/lib:$$PYTHONPATH PATH=${TOP}/configtools/build/bin:$$PATH getconf.py test-repodir $(prog) repo)
repo        = ${repouser}@${repohost}:${repodir}
testrepo    = ${repouser}@${repohost}:${testrepodir}

# how to push it to ${repohost}
# old versions are *NOT* deleted, so periodic hand-pruning will be necessary.
.PHONY: push
push:: rpm-copy
	for d in 6Server 7Server 20 21 22 ;do \
		rsync -ave ssh ${HOME}/rpmbuild/RPMS/$$d/ ${repo}/$$d; \
		ssh ${repouser}@${repohost} "cd ${repodir}/$$d; rm -rf repodata; createrepo ." \
	;done || echo "Maybe remove .rpm-copy and try again?"

.PHONY: update-pbench-repo
update-pbench-repo::
	for d in 6Server 7Server 20 21 22 ;do \
		ls -ld ${HOME}/rpmbuild/RPMS/$$d/ ; \
		ssh ${repouser}@${repohost} "cd ${repodir}/$$d; rm -rf repodata; createrepo ." \
	;done || echo "Maybe remove .rpm-copy and try again?"

# we do not delete older test rpms automatically- they are supposed to be
# installed using the full version-release string, so multiple versions
# should not cause problems.
.PHONY: push-test-rpm
push-test-rpm: rpm-copy
	for d in 6Server 7Server 20 21 22 ;do \
		rsync -ave ssh ${HOME}/rpmbuild/RPMS/$$d/ ${testrepo}/$$d; \
		ssh ${repouser}@${repohost} "cd ${testrepodir}/$$d; rm -rf repodata; createrepo ." \
	;done || echo "Maybe remove .rpm-copy and try again?"

# I can never remember what I called it.
.PHONY: test-rpm push-test
test-rpm: push-test-rpm
push-test: push-test-rpm

.PHONY: clean-test-rpm
clean-test-rpm:
	ssh ${repouser}@${repohost} 'cd ${testrepodir}; rm -f */x86_64/${prog}*.rpm'

.PHONY: clean-test
clean-test: clean-test-rpm

# The default clean target
clean:: clean-build dot-clean

# A simple rule to facilitate making all test RPMs
.PHONY: all-test
all-test: clean-test all push-test
