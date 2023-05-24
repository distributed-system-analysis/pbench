# Build Requirements

Container image building requires both the `buildah` and `jinja2` CLI commands
to be present.

On Fedora 35 and later systems, use the following command to install the
required CLI interface RPMs:

    sudo dnf install buildah python3-jinja2-cli

# Notes

  * We currently only support building container images from previously built
    RPMs in an accessible yum/dnf set of repos

  * We currently only support container images built from `x86_64` architecture
    RPMs

  * Visualizers have been moved to a new repo, source code can be found at:
    [distributed-system-analysis/visualizers](https://github.com/distributed-system-analysis/visualizers)

# How to Use

The first step is taken elsewhere, where one would build `pbench-agent`, and
`pbench-sysstat` RPMs, build or find proper RPMs for `fio` & `uperf`, and place
them in a single yum/dnf repository accessible via HTTPS.  By default, we use
Fedora COPR repos under the `ndokos` user (one can override the yum/dnf repos
and user via the `URL_PREFIX` and `USER` environment variables, and use
`pbench-test` repos by setting the `TEST` environment variable to `test`).

Once the proper RPMs are available in the target repo, the default `Makefile`
target, `everything`, will build each default image, and tag them with the
pbench-agent RPM version and git commit hash ID.  E.g., when done, one might
see output from `buildah images` that looks like:

```
$ make everything
.
. (lots of build output here ...)
.
$ buildah images
.
.
.
localhost/pbench-agent-base-centos-7  958aeba4   5499e5521f50 ...
localhost/pbench-agent-base-centos-7  v0.69.3-1  5499e5521f50 ...
localhost/pbench-agent-all-centos-8   958aeba4   9396f0337681 ...
localhost/pbench-agent-all-centos-8   v0.69.3-1  9396f0337681 ...
.
.
.
```

There are make targets for each of the five supported distributions, CentOS 9
(`centos-9`), CentOS 8 (`centos-8`), CentOS 7 (`centos-7`), Fedora 38
(`fedora-38`), and Fedora 37 (`fedora-37`).  There are also make targets for
each subset of the container image kinds (`all`, `tool-data-sink`,
`tool-meister`, `tools`, `workloads`, `base`) built for each distribution, e.g.
`centos-8-tools-tagged`, `fedora-35-base-tagged`, etc.

Two tags are always applied to an image that is built, the `<git commit ID>`
derived from the RPM version, and the version string of the RPM itself (without
the trailing commit ID).

One can add additional local tags using the following targets when appropriate
(these tags are not automatically applied at build time):

 * `tag-latest` - adds the `latest` label to the images with the
   `<git commit ID>` as derived from the RPM version string of the pbench-agent
   RPM

 * `tag-major` - adds the `v<Major>-latest` label to the images as derived from
   the RPM version string ...

 * `tag-major-minor` -adds the `v<Major>.<Minor>-latest` label to the images ...

 * `tag-alpha` - adds the `alpha` label to the images ...

 * `tag-beta` - adds the `beta` label to the images ...

Finally, there are "push" targets to copy the locally built and tagged images
to a non-local container image repository.  By default we use
`docker://quay.io/pbench` (you can override that via the environment variable
`IMAGE_REPO`).  We have separate push targets to allow the administrator of the
container image repository to label the images based on what they have built in
relation to what has been published already.  The push targets are:

 * `push` - pushes each image by its `<git commit ID>` tag, and its RPM version
   tag

 * `push-latest` - pushes each image by its `latest` tag

 * `push-major` - pushes each image by its `v<Major>-latest` tag

 * `push-major-minor` - pushes each image by its `v<Major>.<Minor>-latest` tag

 * `push-alpha` - pushes each image by its `alpha` tag

 * `push-beta` - pushes each image by its `beta` tag

There is also a special "push" target `publish` which pushes all the
containers for each of the default distributions, but it pushes only the one
tag defined by `IMAGE_TAG` and not the RPM version or Git hash tags.

**_NOTE WELL_**: Each separate tag for each image needs to be pushed to the
non-local container image repository.  This does NOT result in multiple image
copies over the wire using up network bandwidth, as `buildah push` is smart
enough to push the actual image only once.

# Detailed list of external Make targets

These act on the default platforms' containers:

 * `everything` (default):  make every image for the default platforms
 * `baseimage`: make Agent base images for the default platforms
 * `tds`:  make Tool Data Sink images for the default platforms
 * `tm`:  make Tool Meister images for the default platforms
 * `tag-<TYPE>` (e.g., "tag-latest"):  apply specified tag to every image for
   the default platforms
 * `push`:  push images for the default platforms with `<git commit hash>`
   and `v<full RPM version>` tags
 * `push-<TYPE>` (e.g., "push-latest"):  push images for the default
   platforms with specified tag

These act on the indicated distribution's containers:

 * `<DISTRO>` (e.g., "fedora-34"):  make every image kind for the distribution
 * `<DISTRO>-baseimage` (e.g., "fedora-34-baseimage"):  make the Agent base image for the distro
 * `<DISTRO>-tds` (e.g., "fedora-34-tds"):  make the TDS image for the distro
 * `<DISTRO>-tm` (e.g., "fedora-34-tm"):  make the TM image for the distro
 * `<DISTRO>-tag-<TYPE>` (e.g., "fedora-34-tag-alpha"):  apply the specified
   tag to the distro containers
 * `<DISTRO>-push` (e.g., "fedora-34-push"):  push the specified containers
 * `<DISTRO>-push-<TYPE>` (e.g., "fedora-34-push-alpha"):  push the specified
   containers

_NOTE_: the supported distributions are listed above.

Further, each container has its own build target per distribution:

 * `<DISTRO>-all[-tagged]`:  depends on others below
   _NOTE_: the "all" here is the kind of container, which is composed of 
   the combined contents of the other containers for a <DISTRO>
 * `<DISTRO>-tool-data-sink[-tagged]`:  depends on <DISTRO>-tools-tagged
 * `<DISTRO>-tool-meister[-tagged]`:  depends on <DISTRO>-tools-tagged
 * `<DISTRO>-tools[-tagged]`:  depends on <DISTRO>-base-tagged
 *  `<DISTRO>-workloads[-tagged]`:  depends on <DISTRO>-base-tagged
 * `<DISTRO>-base[-tagged]`

Utility targets:

 * `clean`:  remove build artifacts
 * `pkgmgr-clean`:  clear the local package manager cache
 * `all-tags`:  build all default distro "-tags.lis" files and verify that they
   are consistent
 * `all-dockerfiles`:  build all default distro ".repo" and ".Dockerfile" files

_NOTE_: for debugging purposes, you can set the environment variable,
`BUILDAH_ECHO`, to the value of `echo` to prevent container build operations
from taking place. This behavior allows a person to quickly see all the build
steps and their output.
