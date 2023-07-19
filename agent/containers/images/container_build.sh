#!/bin/bash

# This is an essentially "trivial" script to interactively build a full set of
# Pbench Agent containers for a platform specified by the PB_AGENT_DISTRO
# environment variable, defaulting to fedora-38.
#
# This is similar to the commands used in the CI; however, the CI builds the
# RPMs in the common build.sh script while the Jenkins Pipeline.gy builds the
# CI container on top of that. This encapsulates the "trickery" used to get a
# functional result so it's easier to use interactively.
#
# For efficiency, we don't use the various "cleanup" Make targets; however
# instead of needing to remember and execute them separately, you can use
#   agent/containers/images/container_build.sh --clean
# to insert the cleanup targets when desirable.

opts=$(getopt -q -o ch --longoptions "clean,help" -n "container_build" -- "${@}")
if [[ ${?} -ne 0 ]]; then
    printf -- "%s %s\n\n\tunrecognized option specified\n\n" "${0}" "${*}" >&2
    usage >&2
    exit 1
fi
eval set -- "${opts}"
rpm_clean=
pod_clean=
while true; do
    arg=${1}
    shift
    case "${arg}" in
    -c|--clean)
        rpm_clean=distclean
        pod_clean=clean
        ;;
    -h|--help)
        usage
        exit 0
        ;;
    --)
        break
        ;;
    *)
        printf -- "${0}: unrecognized command line argument, '${arg}'\n" >&2
        usage >&2
        exit 1
        ;;
    esac
done

PB_AGENT_DISTRO=${PB_AGENT_DISTRO:-fedora-38}

WORKSPACE_TMP=${HOME} make -C agent/rpm ${rpm_clean} ${PB_AGENT_DISTRO}-rpm
CI=1 WORKSPACE_TMP=${HOME} make -C agent/containers/images \
    CI_RPM_ROOT=${HOME} ${pod_clean} ${PB_AGENT_DISTRO}-everything
