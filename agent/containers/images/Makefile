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

# Default we build images the following distributions:
all: centos-8-all-tagged centos-7-all-tagged fedora-32-all-tagged fedora-31-all-tagged

latest: centos-8-latest centos-7-latest fedora-32-latest fedora-31-latest

major: centos-8-major centos-7-major fedora-32-major fedora-31-major

major-minor: centos-8-major-minor centos-7-major-minor fedora-32-major-minor fedora-31-major-minor

#+
# For the following rule patterns, the "%" represents, or represents
# the "distribution" name, as derived from the "all" target's *-distro
# list.
#-

%-all-tagged: %-all %-tags.lis
	./apply-tags pbench-agent-all-${@:-all-tagged=} ${@:-all-tagged=}-tags.lis

%-all: %-tools-tagged %-workloads-tagged %-all.Dockerfile
	./build-image all ${@:-all=} ${@:-all=}-tags.lis

%-all.Dockerfile: Dockerfile.layered.j2
	jinja2 Dockerfile.layered.j2 -D distro=${@:-all.Dockerfile=} -D kind="all" -D rpms="${_ALL_RPMS}" > ./$@

%-tools-tagged: %-tools %-tags.lis
	./apply-tags pbench-agent-tools-${@:-tools-tagged=} ${@:-tools-tagged=}-tags.lis

%-tools: %-base-tagged %-tools.Dockerfile
	./build-image tools ${@:-tools=} ${@:-tools=}-tags.lis

%-tools.Dockerfile: Dockerfile.layered.j2
	jinja2 Dockerfile.layered.j2 -D distro=${@:-tools.Dockerfile=} -D kind="tools" -D rpms="${_TOOL_RPMS}" > ./$@

%-workloads-tagged: %-workloads %-tags.lis
	./apply-tags pbench-agent-workloads-${@:-workloads-tagged=} ${@:-workloads-tagged=}-tags.lis

%-workloads: %-base-tagged %-workloads.Dockerfile
	./build-image workloads ${@:-workloads=} ${@:-workloads=}-tags.lis

%-workloads.Dockerfile: Dockerfile.layered.j2
	jinja2 Dockerfile.layered.j2 -D distro=${@:-workloads.Dockerfile=} -D kind="workloads" -D rpms="${_WORKLOAD_RPMS}" > ./$@

%-base-tagged: %-base
	./apply-tags pbench-agent-base-${@:-base-tagged=} ${@:-base-tagged=}-tags.lis

%-base: %-base.Dockerfile %-tags.lis
	./build-image base ${@:-base=} ${@:-base=}-tags.lis

%-tags.lis:
	./gen-tags-from-rpm "${URL_PREFIX}" "${@:-tags.lis=}" "${_ARCH}" > ${@}

#+
# Simple pattern rule label the current RPM version the latest.
#-

%-latest: %-tags.lis
	./tagit ${@:-latest=} latest

%-major: %-tags.lis
	./tagit ${@:-major=} major-latest

%-major-minor: %-tags.lis
	./tagit ${@:-major-minor=} major-minor-latest

#+
# For the following rules, the various CentOS "base" images need a maping
# between the # distribution name and the repo name, which for CentOS images
# is "epel".  And for both CentOS and Fedora the distribution image reference
# the package manager (dnf vs yum), and image name also require a mapping
# (e.g. centos-7 -> yum, centos:7, CentOS 7, fedora-32 -> dnf, fedora:32,
# Fedora 32).
#-
centos-8-base.Dockerfile: Dockerfile.base.j2 epel-8-pbench.repo
	jinja2 Dockerfile.base.j2 -D pbench_repo_file=epel-8-pbench.repo -D pkgmgr=dnf -D distro_image=centos:8 -D distro_image_name="CentOS 8" -o $@

centos-7-base.Dockerfile: Dockerfile.base.j2 epel-7-pbench.repo
	jinja2 Dockerfile.base.j2 -D pbench_repo_file=epel-7-pbench.repo -D pkgmgr=yum -D distro_image=centos:7 -D distro_image_name="CentOS 7" -o $@

fedora-32-base.Dockerfile: Dockerfile.base.j2 fedora-32-pbench.repo
	jinja2 Dockerfile.base.j2 -D pbench_repo_file=fedora-32-pbench.repo -D pkgmgr=dnf -D distro_image=fedora:32 -D distro_image_name="Fedora 32" -o $@

fedora-31-base.Dockerfile: Dockerfile.base.j2 fedora-31-pbench.repo
	jinja2 Dockerfile.base.j2 -D pbench_repo_file=fedora-31-pbench.repo -D pkgmgr=dnf -D distro_image=fedora:31 -D distro_image_name="Fedora 31" -o $@

# Rule pattern dependencies on non-patterned targets have to be setup
# separately for some reason.
%.repo: ${_REPO_TEMPLATE} 

%.repo: %.yml
	jinja2 ${_REPO_TEMPLATE} ${@:.repo=}.yml -o $@

%.yml: repo.yml.j2
	jinja2 repo.yml.j2 -D distro=${@:-pbench.yml=} -D url_prefix=${URL_PREFIX} -o $@

clean:
	rm -f *.Dockerfile *.repo *.yml *-tags.lis
