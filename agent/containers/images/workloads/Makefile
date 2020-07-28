distros = centos-8 centos-7 fedora-32 fedora-31

all: ${distros}

${distros}: clean
	jinja2 Dockerfile.j2 -D distro=$@ > ./Dockerfile
	buildah bud -t pbench-agent-workloads-$@:latest .
	# buildah push pbench-agent-workloads-$@:latest docker://quay.io/pbench/pbench-agent-workloads-$@:latest

clean:
	rm -rf Dockerfile
