# A simple Makefile for building and pushing the pbench-devel
# container image.

BRANCH := $(shell cat ./branch.name)

all: image

push:
	buildah push localhost/pbench-devel:${BRANCH} quay.io/pbench/pbench-devel:${BRANCH}

image:
	buildah bud -f development.Dockerfile -t localhost/pbench-devel:${BRANCH}
