# Base Makefile for building all images and tagging them

# List of external Make targets:
#
#   These act on all default platforms' containers:
#
#     all (default):  make all images for all default platforms
#     tds:  make Tool Data Sink images for all default platforms
#     tm:  make Tool Meister images for all default platforms
#     tag-<TYPE> (e.g., "tag-latest"):  apply specified tag to all images for all default platforms
#     push:  push images for all default platforms with "<git commit hash>" and "v<full RPM version>" tags
#     push-<TYPE> (e.g., "push-latest"):  push images for all default platforms with specified tag
#
#   These act on the indicated distribution's containers:
#
#     <DISTRO> (e.g., "fedora-34"):  make all images for the requested platform
#     <DISTRO>-tds (e.g., "fedora-34-tds"):  make the TDS image for the requested platform
#     <DISTRO>-tm (e.g., "fedora-34-tm"):  make the TM image for the requested platform
#     <DISTRO>-tag-<TYPE> (e.g., "fedora-34-tag-alpha"):  apply the specified tag to the distro containers
#     <DISTRO>-push (e.g., "fedora-34-push"):  push the specified containers
#     <DISTRO>-push-<TYPE> (e.g., "fedora-34-push-alpha"):  push the specified containers
#
#   Utility targets:
#
#     clean:  remove build artifacts
#     pkgmgr-clean:  clear the local package manager cache
#     all-tags:  build all default distro "-tags.lis" files and verify that they are consistent.
#     all-dockerfiles:  build all default distro ".repo" and ".Dockerfile" files
#

# Include definition of _DISTROS
include ../utils/utils.mk

# By default we only build images for x86_64 architectures.
_ARCH = x86_64

# By default we use this user's account on Fedora COPR for where to
# find the RPMs.  You can override this using an environment variable
# as appropriate.
COPR_USER = ndokos

# By default we use Fedora COPR repos. You can override this default
# using an environment variable as appropriate.
URL_PREFIX = https://copr-be.cloud.fedoraproject.org/results/${COPR_USER}

# By default we use non-"test" COPR repos named "pbench".  We expect
# test COPR repos to have a suffix added, typically "test", so that
# the final repo name would be "pbench-test".
TEST =
_TEST_SUFFIX = $(if $(TEST),-$(TEST),"")
_PBENCH_REPO_NAME = pbench${_TEST_SUFFIX}

# By default we use the pbench Quay.io organization for the image
# repository.  You can override this default using an environment
# variable as appropriate.
IMAGE_REPO = docker://quay.io/pbench

# Convenience reference to the repo template in the pbench tree.
# Not intended to be overridden with an environment variable.
_PBENCH_REPO_TEMPLATE = ../../ansible/roles/pbench_repo_install/templates/etc/yum.repos.d/pbench.repo.j2

# This is for use on CentOS; on Fedora, the package is available without a
# custom .repo file.
_PROMETHEUS_REPO_URL = https://packagecloud.io/install/repositories/prometheus-rpm/release/config_file.repo?os=el&dist=${DIST_VERSION}&source=script

# This list of PCP RPMs we need to provide all the required features.  We use
# pcp-gui to ensure pmchart is installed in the tools container so that users
# have a native way to review PCP data.  The pcp-zeroconf RPM provides a
# comprehensive set of pre-configurations for various PMDAs.  Finally, the
# pcp-system-tools various "sysstat" replacement tools (along with others),
# and the dependency on the base `pcp` package.
_PCP_RPMS = \
	pcp-gui \
	pcp-system-tools \
	pcp-zeroconf

# The list of RPMs which provide the various tools we offer.
# Not intended to be overridden with an environment variable.
# Please keep the lists sorted.
_TOOL_RPMS = \
	blktrace \
	bpftrace \
	cpupowerutils \
	golang \
	kernel-tools \
	libvirt-client \
	nmap-ncat \
	numactl \
	pbench-sysstat \
	${_PCP_RPMS} \
	perf \
	procps-ng \
	${_PROMETHEUS_RPMS} \
	strace \
	tcpdump \
	trace-cmd

# The list of RPMs for the default workloads we offer.
# Not intended to be overridden with an environment variable.
_WORKLOAD_RPMS = fio uperf

# Not intended to be overridden with an environment variable.
_ALL_RPMS = ${_TOOL_RPMS} ${_WORKLOAD_RPMS}

# By default we only build images for the following distributions.
_DEFAULT_DISTROS = centos-7 centos-8 centos-9 fedora-35

# By default we build the Tool Data Sink and Tool Meister images as well.
all: pkgmgr-clean all-tags $(_DEFAULT_DISTROS:%=%-all-tagged)

# Convenience target to only build the Tool Data Sink images.
tds: pkgmgr-clean all-tags $(_DEFAULT_DISTROS:%=%-tool-data-sink-tagged)

# Convenience target to only build the Tool Meister images.
tm: pkgmgr-clean all-tags $(_DEFAULT_DISTROS:%=%-tool-meister-tagged)

#+
# For the following rule patterns, the "%" represents the "distribution" name,
# e.g., as derived from the _DEFAULT_DISTROS list.
#
# The string matching the "%" is called the "stem", in GNU Make parlance.  The
# "$*" references are replaced with that stem value.
#
# See https://www.gnu.org/software/make/manual/make.html#Automatic-Variables
#-

# We also offer targets per distribution target
${_DISTROS}: %: pkgmgr-clean %-all-tagged

$(_DISTROS:%=%-tds): %-tds: pkgmgr-clean %-tool-data-sink-tagged

$(_DISTROS:%=%-tm): %-tm: pkgmgr-clean %-tool-meister-tagged

# For any given target, extract the distribution name and version from the
# first two fields, e.g., fedora-35-tds would yield values "fedora" and "35"
# for DIST_NAME and DIST_VERSION, respectively.
%: DIST_NAME = $(wordlist 1, 1, $(subst -, ,$*))
%: DIST_VERSION = $(wordlist 2, 2, $(subst -, ,$*))

# These are the lists of Prometheus RPMs -- the packages are the same, but they
# have different names in the different distributions
fedora-% centos-9-%: _PROMETHEUS_RPMS = \
    golang-github-prometheus-node-exporter \
    golang-github-prometheus
centos-7-% centos-8-%: _PROMETHEUS_RPMS = \
    node_exporter \
    prometheus2


# Tagging targets
#
# Available tags values are "latest", "alpha", "beta", "major", and "major-minor"
# "major" produces a tag of "v<Major>-latest", and "major-minor" produces a tag
# of "v<Major>.<Minor>-latest".
#
# See the `tagit` script for details.
_TAG_TYPES = latest alpha beta major major-minor
$(_TAG_TYPES:%=tag-%): tag-%: $(_DEFAULT_DISTROS:%=%-tag-%)


#+
# Push targets
#-

# Push images with "<git commit hash>" and "v<full RPM version>" tags.
push: $(_DEFAULT_DISTROS:%=%-push)

# Push images with a specific tag (see the `tag-%` target).
$(_TAG_TYPES:%=push-%): push-%: $(_DEFAULT_DISTROS:%=%-push-%)


#+
# Ensure repos exist with correct visibility and permissions.
#-
repofix: $(_DEFAULT_DISTROS:%=%-repofix)


#+
# Build targets
#-

%-all-tagged: %-all %-tags.lis
	./apply-tags pbench-agent-all-$* $*-tags.lis

%-all: %-workloads-tagged %-tool-data-sink-tagged %-tool-meister-tagged %-all.Dockerfile %-tags.lis
	./build-image all $* $*-tags.lis

%-all.Dockerfile: Dockerfile.layered.j2 %-tags.lis
	jinja2 Dockerfile.layered.j2 -D distro=$* -D tag="$$(grep -v -E '^v' $*-tags.lis)" \
		-D kind="all" -D rpms="${_ALL_RPMS}" > ./$@

%-tool-data-sink-tagged: %-tool-data-sink %-tags.lis
	./apply-tags pbench-agent-tool-data-sink-$* $*-tags.lis

%-tool-data-sink: %-tools-tagged %-tool-data-sink.Dockerfile %-tags.lis
	./build-image tool-data-sink $* $*-tags.lis

%-tool-data-sink.Dockerfile: Dockerfile.tds.j2 %-tags.lis
	jinja2 Dockerfile.tds.j2 -D distro=$* -D tag="$$(grep -v -E '^v' $*-tags.lis)" > ./$@

%-tool-meister-tagged: %-tool-meister %-tags.lis
	./apply-tags pbench-agent-tool-meister-$* $*-tags.lis

%-tool-meister: %-tools-tagged %-tool-meister.Dockerfile %-tags.lis
	./build-image tool-meister $* $*-tags.lis

%-tool-meister.Dockerfile: Dockerfile.tm.j2 %-tags.lis
	jinja2 Dockerfile.tm.j2 -D distro=$* -D tag="$$(grep -v -E '^v' $*-tags.lis)" > ./$@

%-tools-tagged: %-tools %-tags.lis
	./apply-tags pbench-agent-tools-$* $*-tags.lis

# CentOS 7 & 8 (but not 9) require an additional .repo file for Prometheus for
# the tools container; analogously, they as well as Fedora require an additional
# .repo file for PCP.
centos-7-tools centos-8-tools: centos-%-tools: centos-%-prometheus.repo
$(_ALL_fedora_VERSIONS:%=%-tools) centos-7-tools centos-8-tools: %-tools: %-pcp.repo

%-tools: %-base-tagged %-tools.Dockerfile %-tags.lis
	./build-image tools $* $*-tags.lis

%-tools.Dockerfile: Dockerfile.layered.j2 %-tags.lis
	jinja2 Dockerfile.layered.j2 -D distro=$* -D tag="$$(grep -v -E '^v' $*-tags.lis)" \
		-D kind="tools" -D rpms="${_TOOL_RPMS}" > ./$@

%-workloads-tagged: %-workloads %-tags.lis
	./apply-tags pbench-agent-workloads-$* $*-tags.lis

%-workloads: %-base-tagged %-workloads.Dockerfile %-tags.lis
	./build-image workloads $* $*-tags.lis

%-workloads.Dockerfile: Dockerfile.layered.j2 %-tags.lis
	jinja2 Dockerfile.layered.j2 -D distro=$* -D tag="$$(grep -v -E '^v' $*-tags.lis)" \
		-D kind="workloads" -D rpms="${_WORKLOAD_RPMS}" > ./$@

%-base-tagged: %-base %-tags.lis
	./apply-tags pbench-agent-base-$* $*-tags.lis

%-base: %-base.Dockerfile %-pbench.repo %-tags.lis
	./build-image base $* $*-tags.lis

#+
# Push local images for the given tag and distribution.
#-

define _PUSH_RULE
%-push-$(1): %-tags.lis
	./push ${IMAGE_REPO} $$* $(1)
endef

$(foreach tagtype,${_TAG_TYPES},$(eval $(call _PUSH_RULE,${tagtype})))  # Define rules

%-push: %-tags.lis
	./push ${IMAGE_REPO} $*

#+
# Invoke quay-repo to force visibility and permission change
#-

%-repofix:
	./repo-fix $*

#+
# Tag local images for the given distribution.
#
# "major" produces a tag of "v<Major>-latest", and "major-minor" produces a tag
# of "v<Major>.<Minor>-latest".  (See the `tag-%` target.)
#-

define _TAG_RULE
%-tag-$(1): %-tags.lis
	./tagit $$* $(1)$(if $(findstring major,$(1)),-latest)
endef

$(foreach tagtype,${_TAG_TYPES},$(eval $(call _TAG_RULE,${tagtype})))  # Define rules

# Build the tags file for the given distribution. (We rename "centos" to "epel".)
%-tags.lis:
	./gen-tags-from-rpm "${URL_PREFIX}" "$(subst centos,epel,$*)" "${_ARCH}" "${_PBENCH_REPO_NAME}" > ${@}

# This file takes a long time to generate, so preserve it between builds (it can
# be removed explicitly via the `clean` target).
.PRECIOUS:: %-tags.lis

# Helper target to ensure local cache consistent by "cleaning"
pkgmgr-clean:
	dnf clean all

#+
# For the following rules, the various CentOS "base" images need a mapping
# between the distribution name and the repo name, which for CentOS images
# is "epel".  And for both CentOS and Fedora, the distribution image
# reference, the package manager (dnf vs yum), and image name, also require
# mappings (e.g. centos-7 -> yum, centos:7, CentOS 7, fedora-32 -> dnf,
# fedora:32, Fedora 32).
#-
_PKGMGR = dnf
centos-7-base.Dockerfile: _PKGMGR = yum

centos-%-base.Dockerfile: Dockerfile.base.j2
	jinja2 Dockerfile.base.j2 -D pbench_repo_file=centos-$*-pbench.repo \
        -D pkgmgr=${_PKGMGR} -D distro_name="CentOS $*" -o $@ \
        -D image_repo=quay.io/centos -D image_name=centos -D image_rev=$*

fedora-%-base.Dockerfile: Dockerfile.base.j2
	jinja2 Dockerfile.base.j2 -D pbench_repo_file=fedora-$*-pbench.repo \
        -D pkgmgr=dnf -D distro_name="Fedora $*" -o $@ \
        -D image_repo=quay.io/fedora -D image_name=fedora -D image_rev=$*

# Helper target to build each distro's ".repo" and ".Dockerfile"
all-dockerfiles: \
    $(_DEFAULT_DISTROS:%=%-base.Dockerfile) $(_DEFAULT_DISTROS:%=%-tools.Dockerfile) \
    $(_DEFAULT_DISTROS:%=%-workloads.Dockerfile) $(_DEFAULT_DISTROS:%=%-all.Dockerfile)

# Helper target to build each distro's "-tags.lis" file and verify they
# are consistent.
all-tags: pkgmgr-clean $(_DEFAULT_DISTROS:%=%-tags.lis)
	./verify-tags *-tags.lis

%-pbench.repo: %-pbench.yml ${_PBENCH_REPO_TEMPLATE}
	jinja2 ${_PBENCH_REPO_TEMPLATE} $*-pbench.yml -o $@

%-pbench.yml: repo.yml.j2
	jinja2 repo.yml.j2 -D name=${_PBENCH_REPO_NAME} -D user=${COPR_USER} \
        -D distro=$(if $(filter centos,${DIST_NAME}),$(subst centos,epel,$*),$*) \
        -D url_prefix=${URL_PREFIX} -o $@

%-pcp.repo: pcp.repo.j2
	jinja2 pcp.repo.j2 -D distro=${DIST_NAME} -D version=${DIST_VERSION} -o $@

%-prometheus.repo:
	curl -sSf "${_PROMETHEUS_REPO_URL}" > $@

clean:
	rm -f *.Dockerfile *.repo *.yml *-tags.lis
