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

# By default we use the pbench Quay.io organization for the image
# repository.  You can override this default using an environment
# variable as appropriate.
IMAGE_REPO = docker://quay.io/pbench

# Convenience reference to the repo template in the pbench tree.
# Not intended to be overridden with an environment variable.
_REPO_TEMPLATE = ../../ansible/pbench/agent/roles/pbench_repo_install/templates/etc/yum.repos.d/pbench.repo.j2

# The list of RPMs which provide the various tools we offer.
# Not intended to be overridden with an environment variable.
_TOOL_RPMS = pbench-sysstat perf blktrace bpftrace numactl pcp-system-tools strace kernel-tools tcpdump

# The list of RPMs for the default workloads we offer.
# Not intended to be overridden with an environment variable.
_WORKLOAD_RPMS = fio uperf

# Not intended to be overridden with an environment variable.
_ALL_RPMS = ${_TOOL_RPMS} ${_WORKLOAD_RPMS}

_DISTROS = centos-8 centos-7 fedora-32 fedora-31

# Default we only build images the following distributions:
all: $(foreach distro, ${_DISTROS}, ${_DISTROS}-all-tagged)

#+
# Tagging targets
#-

# Add the "latest" tag to the local images.
tag-latest: $(foreach distro, ${_DISTROS}, ${_DISTROS}-tag-latest)

# Add the "v<Major>-latest" tag to the local images.
tag-major: $(foreach distro, ${_DISTROS}, ${_DISTROS}-tag-major)

# Add the "v<Major>.<Minor>-latest" tag to the local images.
tag-major-minor: $(foreach distro, ${_DISTROS}, ${_DISTROS}-tag-major-minor)

#+
# Push targets
#-

# Push images with "<git commit hash>" and "v<full RPM version>" tags.
push: $(foreach distro, ${_DISTROS}, ${_DISTROS}-push)

# Push images with the "latest" tag.
push-latest: $(foreach distro, ${_DISTROS}, ${_DISTROS}-push-latest)

# Push images with the "v<Major>-latest" tag.
push-major: $(foreach distro, ${_DISTROS}, ${_DISTROS}-push-major)

# Push images with the "v<Major>.<Minor>-latest" tag.
push-major-minor: $(foreach distro, ${_DISTROS}, ${_DISTROS}-push-major-minor)

#+
# For the following rule patterns, the "%" represents the "distribution" name,
# as derived from the "all" target's *-distro list.
#-

%-all-tagged: %-all %-tags.lis
	./apply-tags pbench-agent-all-${@:-all-tagged=} ${@:-all-tagged=}-tags.lis

%-all: %-tools-tagged %-workloads-tagged %-all.Dockerfile
	./build-image all ${@:-all=} ${@:-all=}-tags.lis

%-all.Dockerfile: Dockerfile.layered.j2 %-tags.lis
	jinja2 Dockerfile.layered.j2 -D distro=${@:-all.Dockerfile=} -D tag="$$(grep -v -E '^v' ${@:-all.Dockerfile=}-tags.lis)" -D kind="all" -D rpms="${_ALL_RPMS}" > ./$@

%-tools-tagged: %-tools %-tags.lis
	./apply-tags pbench-agent-tools-${@:-tools-tagged=} ${@:-tools-tagged=}-tags.lis

%-tools: %-base-tagged %-tools.Dockerfile
	./build-image tools ${@:-tools=} ${@:-tools=}-tags.lis

%-tools.Dockerfile: Dockerfile.layered.j2 %-tags.lis
	jinja2 Dockerfile.layered.j2 -D distro=${@:-tools.Dockerfile=} -D tag="$$(grep -v -E '^v' ${@:-tools.Dockerfile=}-tags.lis)" -D kind="tools" -D rpms="${_TOOL_RPMS}" > ./$@

%-workloads-tagged: %-workloads %-tags.lis
	./apply-tags pbench-agent-workloads-${@:-workloads-tagged=} ${@:-workloads-tagged=}-tags.lis

%-workloads: %-base-tagged %-workloads.Dockerfile
	./build-image workloads ${@:-workloads=} ${@:-workloads=}-tags.lis

%-workloads.Dockerfile: Dockerfile.layered.j2 %-tags.lis
	jinja2 Dockerfile.layered.j2 -D distro=${@:-workloads.Dockerfile=} -D tag="$$(grep -v -E '^v' ${@:-workloads.Dockerfile=}-tags.lis)" -D kind="workloads" -D rpms="${_WORKLOAD_RPMS}" > ./$@

%-base-tagged: %-base
	./apply-tags pbench-agent-base-${@:-base-tagged=} ${@:-base-tagged=}-tags.lis

%-base: %-base.Dockerfile %-tags.lis
	./build-image base ${@:-base=} ${@:-base=}-tags.lis

#+
# Push local images for the given tag and distribution.
#-

%-push: %-tags.lis
	./push ${IMAGE_REPO} ${@:-push=}

%-push-latest: %-tags.lis
	./push ${IMAGE_REPO} ${@:-push-latest=} latest

%-push-major: %-tags.lis
	./push ${IMAGE_REPO} ${@:-push-major=} _major

%-push-major-minor: %-tags.lis
	./push ${IMAGE_REPO} ${@:-push-major-minor=} _minor

#+
# Tag local images for the given distribution.
#-

%-tag-latest: %-tags.lis
	./tagit ${@:-tag-latest=} latest

%-tag-major: %-tags.lis
	./tagit ${@:-tag-major=} major-latest

%-tag-major-minor: %-tags.lis
	./tagit ${@:-tag-major-minor=} major-minor-latest

# Build the tags file for the given distribution.
%-tags.lis:
	./gen-tags-from-rpm "${URL_PREFIX}" "${@:-tags.lis=}" "${_ARCH}" > ${@}

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
	jinja2 ${_REPO_TEMPLATE} ${@:.repo=}.yml -o $@

%.yml: repo.yml.j2
	jinja2 repo.yml.j2 -D distro=${@:-pbench.yml=} -D url_prefix=${URL_PREFIX} -o $@

clean:
	rm -f *.Dockerfile *.repo *.yml *-tags.lis
