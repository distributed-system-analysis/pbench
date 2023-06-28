#
# A simple Makefile for building and pushing the various pbench-devel-*
# and pbench-rpmbuild container images.
#
# This makefile defines the following targets:
#
#  all (the default):  builds the CI image
#  image-ci:           builds the CI image
#  image-rpmbuild-all: builds all the default containers for building RPMs
#  image-rpmbuild-rhel-7:  builds a single RPM build container (e.g. for RHEL-7)
#  push-ci:            pushes the CI image to the registry
#  push-rpmbuild-all:  pushes all default RPM build containers to the registry
#

# Include definition of _DISTROS
include ../utils/utils.mk

# Default list of distributions for which to build containers in which to build
# RPMs
RPMBUILD_BASEIMAGE_DEFAULTS = \
	rhel-9 rhel-8 rhel-7 \
	fedora-38 fedora-37 \
	centos-9 centos-8 centos-7

CI_BASE_IMAGE = quay.io/fedora/fedora:38

# Templates for the various distributions' base images.  For the moment, for a
# given distribution, all of the versions can be found by tweaking the image
# tag; so, to generate the appropriate repository for the base image, we just
# have to pick the appropriate template and insert the requested version, which
# is exactly what happens when RPMBUILD_BASEIMAGE_REPO is expanded.
#
# Note that registry.access.redhat.com is moving to registry.redhat.io where it
# will no longer permit anonymous access, but it works for the moment.
VER := __version__
RPMBUILD_BASEIMAGE_rhel = registry.access.redhat.com/ubi${VER}:latest
RPMBUILD_BASEIMAGE_fedora = quay.io/fedora/fedora:${VER}
RPMBUILD_BASEIMAGE_centos = quay.io/centos/centos:stream${VER}
RPMBUILD_BASEIMAGE_REPO = $(subst ${VER},${DIST_VERSION},${RPMBUILD_BASEIMAGE_${DIST_NAME}})

# List of packages required to build RPMs, to be installed in the build
# containers.  (python39 is required for the Server build.)
#
# TODO:  The Jinja2 CLI is not currently available as an RPM on RHEL, so we
#        install it via pip for all platforms, to keep things simple; we should
#        reevaluate this dependency in the future.
RPMBUILD_PACKAGES = git make python3-jinja2 python3-pip rpmlint rpm-build python39

# Default package manager tool (may be overridden for some distros)
PKGMGR = dnf

BRANCH := $(shell cat ./branch.name)

# For any given target, extract the distribution name and version from the last
# two fields, e.g., image-rpmbuild-rhel-7 would yield values "rhel" and "7" for
# DIST_NAME and DIST_VERSION, respectively.
%: DIST_VERSION = $(lastword $(subst -, ,$*))
%: DIST_NAME = $(lastword $(subst ${DIST_VERSION},,$(subst -, ,$*)))


all: image-ci

push-rpmbuild-all: $(RPMBUILD_BASEIMAGE_DEFAULTS:%=push-rpmbuild-%)

image-rpmbuild-all: $(RPMBUILD_BASEIMAGE_DEFAULTS:%=image-rpmbuild-%)

push-ci:
	buildah push quay.io/pbench/pbench-ci-fedora:${BRANCH}

image-ci: ci.fedora.Dockerfile
	buildah bud -f ci.fedora.Dockerfile -t quay.io/pbench/pbench-ci-fedora:${BRANCH}

${_DISTROS:%=push-rpmbuild-%}: push-rpmbuild-%:
	buildah push ${PB_CONTAINER_REG}/pbench-rpmbuild:${*}

image-rpmbuild-rhel-7 : PKGMGR = yum
image-rpmbuild-centos-7 : PKGMGR = yum
image-rpmbuild-centos-7 : RPMBUILD_BASEIMAGE_centos = quay.io/centos/centos:centos7

${_DISTROS:%=image-rpmbuild-%}: image-rpmbuild-%:
	container=$$(buildah from ${RPMBUILD_BASEIMAGE_REPO}) && \
		buildah run $$container ${PKGMGR} install -y ${RPMBUILD_PACKAGES} && \
		buildah run $$container ${PKGMGR} clean all && \
		buildah run $$container python3 -m pip install jinja2-cli && \
		buildah commit $$container ${PB_CONTAINER_REG}/pbench-rpmbuild:${*}

ci.fedora.Dockerfile: ci.Dockerfile.j2
	jinja2 ci.Dockerfile.j2 \
		-D base_image_ref="${CI_BASE_IMAGE}" \
		-D fedora=True \
		> $@

clean:
	rm -f development.*.Dockerfile ci.*.Dockerfile
