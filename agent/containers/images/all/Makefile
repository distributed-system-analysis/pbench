distros = centos-8 centos-7 fedora-32 fedora-31

all: ${distros}

${distros}: clean
	jinja2 Dockerfile.j2 -D distro=$@ > ./Dockerfile
	buildah bud -t pbench-agent-all-$@:latest .
	# buildah push pbench-agent-all-$@:latest docker://quay.io/pbench/pbench-agent-all-$@:latest

clean:
	rm -f Dockerfile
