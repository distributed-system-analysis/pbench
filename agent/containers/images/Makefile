# Base Makefile for building all images and tagging them

# By default we only build images for x86_64 architectures.
_ARCH = x86_64

# By default we use this user's account on Fedora COPR for where to
# find the RPMs.  You can override this using an environment variable
# as appropriate.
USER = ndokos

# By default we use Fedora COPR repos. You can override this default
# using an environment variable as appropriate.
URL_PREFIX = https://copr-be.cloud.fedoraproject.org/results/${USER}

# By default we use non-"test" COPR repos named "pbench".  We expect
# test COPR repos to have a suffix added, typically "test", so that
# the final repo name would be "pbench-test".
TEST =
_TEST_SUFFIX = $(if $(TEST),-$(TEST),"")

# By default we use the pbench Quay.io organization for the image
# repository.  You can override this default using an environment
# variable as appropriate.
IMAGE_REPO = docker://quay.io/pbench

# Convenience reference to the repo template in the pbench tree.
# Not intended to be overridden with an environment variable.
_REPO_TEMPLATE = ../../ansible/pbench/agent/roles/pbench_repo_install/templates/etc/yum.repos.d/pbench.repo.j2

# The list of RPMs which provide the various tools we offer.
# Not intended to be overridden with an environment variable.
_TOOL_RPMS = blktrace bpftrace cpupowerutils golang kernel-tools libvirt-client nmap-ncat numactl pbench-sysstat pcp-system-tools perf procps-ng strace tcpdump trace-cmd

# The list of RPMs for the default workloads we offer.
# Not intended to be overridden with an environment variable.
_WORKLOAD_RPMS = fio uperf

# Not intended to be overridden with an environment variable.
_ALL_RPMS = ${_TOOL_RPMS} ${_WORKLOAD_RPMS}

# By default we only build images for the following distributions:
_DISTROS = centos-8 centos-7 fedora-32 fedora-31

all: $(foreach distro, ${_DISTROS}, ${distro}-all-tagged)

#+
# Tagging targets
#-

# Add the "latest" tag to the local images.
tag-latest: $(foreach distro, ${_DISTROS}, ${distro}-tag-latest)

# Add the "v<Major>-latest" tag to the local images.
tag-major: $(foreach distro, ${_DISTROS}, ${distro}-tag-major)

# Add the "v<Major>.<Minor>-latest" tag to the local images.
tag-major-minor: $(foreach distro, ${_DISTROS}, ${distro}-tag-major-minor)

#+
# Push targets
#-

# Push images with "<git commit hash>" and "v<full RPM version>" tags.
push: $(foreach distro, ${_DISTROS}, ${distro}-push)

# Push images with the "latest" tag.
push-latest: $(foreach distro, ${_DISTROS}, ${distro}-push-latest)

# Push images with the "v<Major>-latest" tag.
push-major: $(foreach distro, ${_DISTROS}, ${distro}-push-major)

# Push images with the "v<Major>.<Minor>-latest" tag.
push-major-minor: $(foreach distro, ${_DISTROS}, ${distro}-push-major-minor)

#+
# For the following rule patterns, the "%" represents the "distribution" name,
# as derived from the "all" target's *-distro list.
#
# The string matching the "%" is called the "stem", in GNU Make parlance.  The
# "$*" references are replaced with that stem value.
#
# See https://www.gnu.org/software/make/manual/make.html#Automatic-Variables
#-

%-all-tagged: %-all %-tags.lis
	./apply-tags pbench-agent-all-$* $*-tags.lis

%-all: %-tools-tagged %-workloads-tagged %-all.Dockerfile
	./build-image all $* $*-tags.lis

%-all.Dockerfile: Dockerfile.layered.j2 %-tags.lis
	jinja2 Dockerfile.layered.j2 -D distro=$* -D tag="$$(grep -v -E '^v' $*-tags.lis)" -D kind="all" -D rpms="${_ALL_RPMS}" > ./$@

%-tools-tagged: %-tools %-tags.lis
	./apply-tags pbench-agent-tools-$* $*-tags.lis

%-tools: %-base-tagged %-tools.Dockerfile
	./build-image tools $* $*-tags.lis

%-tools.Dockerfile: Dockerfile.layered.j2 %-tags.lis
	jinja2 Dockerfile.layered.j2 -D distro=$* -D tag="$$(grep -v -E '^v' $*-tags.lis)" -D kind="tools" -D rpms="${_TOOL_RPMS}" > ./$@

%-workloads-tagged: %-workloads %-tags.lis
	./apply-tags pbench-agent-workloads-$* $*-tags.lis

%-workloads: %-base-tagged %-workloads.Dockerfile
	./build-image workloads $* $*-tags.lis

%-workloads.Dockerfile: Dockerfile.layered.j2 %-tags.lis
	jinja2 Dockerfile.layered.j2 -D distro=$* -D tag="$$(grep -v -E '^v' $*-tags.lis)" -D kind="workloads" -D rpms="${_WORKLOAD_RPMS}" > ./$@

%-base-tagged: %-base
	./apply-tags pbench-agent-base-$* $*-tags.lis

%-base: %-base.Dockerfile %-tags.lis
	./build-image base $* $*-tags.lis

#+
# Push local images for the given tag and distribution.
#-

%-push: %-tags.lis
	./push ${IMAGE_REPO} $*

%-push-latest: %-tags.lis
	./push ${IMAGE_REPO} $* latest

%-push-major: %-tags.lis
	./push ${IMAGE_REPO} $* _major

%-push-major-minor: %-tags.lis
	./push ${IMAGE_REPO} $* _minor

#+
# Tag local images for the given distribution.
#-

%-tag-latest: %-tags.lis
	./tagit $* latest

%-tag-major: %-tags.lis
	./tagit $* major-latest

%-tag-major-minor: %-tags.lis
	./tagit $* major-minor-latest

# Build the tags file for the given distribution.
%-tags.lis:
	./gen-tags-from-rpm "${URL_PREFIX}" "$*" "${_ARCH}" "${_TEST_SUFFIX}" > ${@}

#+
# For the following rules, the various CentOS "base" images need a mapping
# between the distribution name and the repo name, which for CentOS images
# is "epel".  And for both CentOS and Fedora, the distribution image
# reference, the package manager (dnf vs yum), and image name, also require
# mappings (e.g. centos-7 -> yum, centos:7, CentOS 7, fedora-32 -> dnf,
# fedora:32, Fedora 32).
#-
centos-8-base.Dockerfile: Dockerfile.base.j2 epel-8-pbench.repo
	jinja2 Dockerfile.base.j2 -D pbench_repo_file=epel-8-pbench.repo -D pkgmgr=dnf -D distro_image=centos:8 -D distro_image_name="CentOS 8" -o $@

centos-7-base.Dockerfile: Dockerfile.base.j2 epel-7-pbench.repo
	jinja2 Dockerfile.base.j2 -D pbench_repo_file=epel-7-pbench.repo -D pkgmgr=yum -D distro_image=centos:7 -D distro_image_name="CentOS 7" -o $@

fedora-32-base.Dockerfile: Dockerfile.base.j2 fedora-32-pbench.repo
	jinja2 Dockerfile.base.j2 -D pbench_repo_file=fedora-32-pbench.repo -D pkgmgr=dnf -D distro_image=fedora:32 -D distro_image_name="Fedora 32" -o $@

fedora-31-base.Dockerfile: Dockerfile.base.j2 fedora-31-pbench.repo
	jinja2 Dockerfile.base.j2 -D pbench_repo_file=fedora-31-pbench.repo -D pkgmgr=dnf -D distro_image=fedora:31 -D distro_image_name="Fedora 31" -o $@

# Rule pattern dependencies on non-patterned targets have to be set up
# separately for some reason.
%.repo: ${_REPO_TEMPLATE}

%.repo: %.yml
	jinja2 ${_REPO_TEMPLATE} $*.yml -o $@

%.yml: repo.yml.j2
	jinja2 repo.yml.j2 -D distro=${@:-pbench.yml=} -D url_prefix=${URL_PREFIX} -D test_suffix=${_TEST_SUFFIX} -D user=${USER} -o $@

clean:
	rm -f *.Dockerfile *.repo *.yml *-tags.lis
