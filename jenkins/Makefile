# A simple Makefile for building and pushing the various pbench-devel-*
# container images.

BRANCH := $(shell cat ./branch.name)

all: image-fedora

push-fedora:
	buildah push localhost/pbench-devel-fedora:${BRANCH} quay.io/pbench/pbench-devel-fedora:${BRANCH}

image-fedora: development.fedora.Dockerfile
	buildah bud -f development.fedora.Dockerfile -t localhost/pbench-devel-fedora:${BRANCH}

image-ubi: development.ubi.Dockerfile
	buildah bud -f development.ubi.Dockerfile -t localhost/pbench-devel-ubi:${BRANCH}

development.fedora.Dockerfile: development.Dockerfile.j2
	jinja2 development.Dockerfile.j2 \
		-D base_image_ref="quay.io/fedora/fedora:34" \
		-D fedora=True \
		> $@

development.ubi.Dockerfile: development.Dockerfile.j2
	jinja2 development.Dockerfile.j2 \
		-D base_image_ref="registry.access.redhat.com/ubi8/ubi-init:8.5" \
		-D ubi=True \
		-D repo_file_url="${REPO_FILE_URL}" \
		-D hosts_file_url="${HOSTS_FILE_URL}" \
		> $@

clean:
	rm -f development.*.Dockerfile
