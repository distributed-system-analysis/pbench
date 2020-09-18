USER = ndokos

ARCH = x86_64

URL_PREFIX = https://copr-be.cloud.fedoraproject.org/results/${USER}

REPO_TEMPLATE = ../../ansible/pbench/agent/roles/pbench_repo_install/templates/etc/yum.repos.d/pbench.repo.j2

TOOL_RPMS = pbench-sysstat perf blktrace bpftrace numactl pcp-system-tools strace kernel-tools tcpdump

WORKLOAD_RPMS = fio uperf

ALL_RPMS = ${TOOL_RPMS} ${WORKLOAD_RPMS}

all: centos-8-all centos-7-all fedora-32-all fedora-31-all

%-all: %-tools %-workloads %-tags.lis
	#jinja2 Dockerfile.layered.j2 -D distro=${@:-all=} -D kind="all" -D rpms="${ALL_RPMS}" > ./$@.Dockerfile
	#buildah bud -f $@.Dockerfile -t pbench-agent-all-${@:-all=}:latest .
	./apply-tags pbench-agent-all-${@:-all=} ${@:-all=}-tags.lis

%-tools: %-base %-tags.lis
	#jinja2 Dockerfile.layered.j2 -D distro=${@:-tools=} -D kind="tools" -D rpms="${TOOL_RPMS}" > ./$@.Dockerfile
	#buildah bud -f $@.Dockerfile -t pbench-agent-tools-${@:-tools=}:latest .
	./apply-tags pbench-agent-tools-${@:-tools=} ${@:-tools=}-tags.lis

%-workloads: %-base %-tags.lis
	#jinja2 Dockerfile.layered.j2 -D distro=${@:-workloads=} -D kind="workloads" -D rpms="${WORKLOAD_RPMS}" > ./$@.Dockerfile
	#buildah bud -f $@.Dockerfile -t pbench-agent-workloads-${@:-workloads=}:latest .
	./apply-tags pbench-agent-workloads-${@:-workloads=} ${@:-workloads=}-tags.lis

centos-8-base: epel-8-pbench.repo epel-8-tags.lis
	#jinja2 Dockerfile.base.j2 -D pbench_repo_file=epel-8-pbench.repo -D pkgmgr=dnf -D distro_image=centos:8 -D distro_image_name="CentOS 8" -o $@.Dockerfile
	#buildah bud -f $@.Dockerfile -t pbench-agent-base-${@:-base=}:latest .
	./apply-tags pbench-agent-base-${@:-base=} epel-8-tags.lis

centos-7-base: epel-7-pbench.repo epel-7-tags.lis
	#jinja2 Dockerfile.base.j2 -D pbench_repo_file=epel-7-pbench.repo -D pkgmgr=yum -D distro_image=centos:7 -D distro_image_name="CentOS 7" -o $@.Dockerfile
	#buildah bud -f $@.Dockerfile -t pbench-agent-base-${@:-base=}:latest .
	./apply-tags pbench-agent-base-${@:-base=} epel-7-tags.lis

fedora-32-base: fedora-32-pbench.repo fedora-32-tags.lis
	#jinja2 Dockerfile.base.j2 -D pbench_repo_file=fedora-32-pbench.repo -D pkgmgr=dnf -D distro_image=fedora:32 -D distro_image_name="Fedora 32" -o $@.Dockerfile
	#buildah bud -f $@.Dockerfile -t pbench-agent-base-${@:-base=}:latest .
	./apply-tags pbench-agent-base-${@:-base=} fedora-32-tags.lis

fedora-31-base: fedora-31-pbench.repo fedora-31-tags.lis
	#jinja2 Dockerfile.base.j2 -D pbench_repo_file=fedora-31-pbench.repo -D pkgmgr=dnf -D distro_image=fedora:31 -D distro_image_name="Fedora 31" -o $@.Dockerfile
	#buildah bud -f $@.Dockerfile -t pbench-agent-base-${@:-base=}:latest .
	./apply-tags pbench-agent-base-${@:-base=} fedora-31-tags.lis

%.repo: ${REPO_TEMPLATE} 

%.repo: %.yml
	jinja2 ${REPO_TEMPLATE} ${@:.repo=}.yml -o $@

%.yml: repo.yml.j2
	jinja2 repo.yml.j2 -D distro=${@:-pbench.yml=} -D url_prefix=${URL_PREFIX} -o $@

%-tags.lis:
	./gen-tags-from-rpm "${URL_PREFIX}" "${@:-tags.lis=}" "${ARCH}" > ${@}

clean:
	rm -f *.Dockerfile *.repo *.yml *-tags.lis
