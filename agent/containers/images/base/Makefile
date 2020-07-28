URL_PREFIX = https://copr-be.cloud.fedoraproject.org/results/ndokos

distros = centos-8 centos-7 fedora-32 fedora-31

all: ${distros}

centos-8: epel-8-repo.yml
	- rm -f ./pbench.repo Dockerfile
	jinja2 ../../../ansible/roles/pbench-repo-install/templates/etc/yum.repos.d/pbench.repo.j2 epel-8-repo.yml -o ./pbench.repo
	jinja2 Dockerfile.j2 -D pkgmgr=dnf -D distro_image=centos:8 -D distro_image_name="CentOS 8" -o Dockerfile
	buildah bud -t pbench-agent-base-$@:latest .
	# buildah push pbench-agent-base-$@:latest docker://quay.io/pbench/pbench-agent-base-$@:latest

centos-7: epel-7-repo.yml
	- rm -f ./pbench.repo Dockerfile
	jinja2 ../../../ansible/roles/pbench-repo-install/templates/etc/yum.repos.d/pbench.repo.j2 epel-7-repo.yml -o ./pbench.repo
	jinja2 Dockerfile.j2 -D pkgmgr=yum -D distro_image=centos:7 -D distro_image_name="CentOS 7" -o Dockerfile
	buildah bud -t pbench-agent-base-$@:latest .
	# buildah push pbench-agent-base-$@:latest docker://quay.io/pbench/pbench-agent-base-$@:latest

fedora-32: fedora-32-repo.yml
	- rm -f ./pbench.repo Dockerfile
	jinja2 ../../../ansible/roles/pbench-repo-install/templates/etc/yum.repos.d/pbench.repo.j2 $@-repo.yml -o ./pbench.repo
	jinja2 Dockerfile.j2 -D pkgmgr=dnf -D distro_image=fedora:32 -D distro_image_name="Fedora 32" -o Dockerfile
	buildah bud -t pbench-agent-base-$@:latest .
	# buildah push pbench-agent-base-$@:latest docker://quay.io/pbench/pbench-agent-base-$@:latest

fedora-31: fedora-31-repo.yml
	- rm -f ./pbench.repo Dockerfile
	jinja2 ../../../ansible/roles/pbench-repo-install/templates/etc/yum.repos.d/pbench.repo.j2 $@-repo.yml -o ./pbench.repo
	jinja2 Dockerfile.j2 -D pkgmgr=dnf -D distro_image=fedora:31 -D distro_image_name="Fedora 31" -o Dockerfile
	buildah bud -t pbench-agent-base-$@:latest .
	# buildah push pbench-agent-base-$@:latest docker://quay.io/pbench/pbench-agent-base-$@:latest

%.yml: repo.yml.j2
	jinja2 repo.yml.j2 -D distro=${@:-repo.yml=} -D url_prefix=${URL_PREFIX} -o $@

clean:
	rm -f Dockerfile pbench.repo epel-*-repo.yml fedora-*-repo.yml
