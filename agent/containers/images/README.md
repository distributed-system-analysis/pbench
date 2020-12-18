# Build Requirements

Container image building requires both the `buildah` and `jinja2` CLI
commands to be present.

On Fedora 31 and later systems, use the following command to install the
required CLI interface RPMs:

    sudo dnf install buildah python3-jinja2-cli

# Notes

  * We currently only support building container images from previously
    built RPMs in an accessible yum/dnf set of repos

  * We currently only support container images built from `x86_64`
    architecture RPMs

# How to Use

The first step is taken elsewhere, where one would build `pbench-agent`,
and `pbench-sysstat` RPMs, build or find proper RPMs for `fio` & `uperf`,
and place them in a single yum/dnf repository accessible via HTTPS.  By
default, we use Fedora COPR repos under the `ndokos` user (one can
override the yum/dnf repos and user via the `URL_PREFIX` and `USER`
environment variables, and use `pbench-test` repos by setting the `TEST`
environment variable to `test`). 

Once the proper RPMs are available in the target repo, the default
`Makefile` target, `all`, will build all the default images, and tag
them with the pbench-agent RPM version and git commit hash ID.  E.g.,
when done, one might see output from `buildah images` that looks like:

```
$ make all
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

There are make targets for each of the four supported distributions,
CentOS 8 (`centos-8`), CentOS 7 (`centos-7`), Fedora 32 (`fedora-32`),
and Fedora 31 (`fedora-31`).  There are also make targets for each
subset of the four images (all, base, tools, workloads) built for
each distribution, e.g. `centos-8-tools`, `fedora-31-base`, etc.

Two tags are always applied to an image that is built, the `<git
commit ID>` derived from the RPM version, and the version string of
the RPM itself (without the trailing commit ID).

One can add additional local tags using the following targets when
appropriate (these tags are not automatically applied at build time):

 * `tag-latest` - adds the `latest` label to the images with the
   `<git commit ID>` as derived from the RPM version string of the
   pbench-agent RPM

 * `tag-major` - adds the `v<Major>-latest` label to the images
   as derived from the RPM version string ...

 * `tag-major-minor` -adds the `v<Major>.<Minor>-latest` label to
   the images ...

 * `tag-alpha` - adds the `alpha` label to the images ...

 * `tag-beta` - adds the `beta` label to the images ...

Finally, there are "push" targets to copy the locally built and
tagged images to a non-local container image repository.  By default
we use `docker://quay.io/pbench` (you can override that via the
environment variable `IMAGE_REPO`).  We have separate push targets to
allow the administrator of the container image repository to label the
images based on what they have built in relation to what has been
published already.  The push targets are:

 * `push` - pushes all the images by their `<git commit ID>` tag,
   and their RPM version tag

 * `push-latest` - pushes all the images by their `latest` tag

 * `push-major` - pushes all the images by their `v<Major>-latest`
   tag

 * `push-major-minor` - pushes all the images by their
   `v<Major>.<Minor>-latest` tag

 * `push-alpha` - pushes all the images by their `alpha` tag

 * `push-beta` - pushes all the images by their `beta` tag

NOTE WELL: Each separate tag for each image needs to be pushed to
the non-local container image repository.  This does NOT result in
multiple image copies over the wire using up network bandwidth, as
`buildah push` is smart enough to push the actual image only once.
