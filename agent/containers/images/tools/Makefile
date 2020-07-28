distros = centos-8 centos-7 fedora-32 fedora-31

all: ${distros}

${distros}: clean
	jinja2 Dockerfile.j2 -D distro=$@ > ./Dockerfile
	buildah bud -t pbench-agent-tools-$@:latest .
	# buildah push pbench-agent-tools-$@:latest docker://quay.io/pbench/pbench-agent-tools-$@:latest

clean:
	rm -rf Dockerfile
