#!/bin/bash

# This is an essentially "trivial" script to interactively build a full set of
# Pbench Agent containers for a platform specified by the PB_AGENT_DISTRO
# environment variable, defaulting to fedora-38.
#
# These are the same commands used in the CI; however, the CI builds the
# RPMs in the common build.sh script while the Jenkins Pipeline.gy builds the
# CI container on top of that. Here we encapsulate the steps used to get a
# functional result to make this more convenient interactively.
#
# WORKSPACE_TMP is assumed to be the root of the work area, and by default will
# be set to ${HOME}.
#
# If you want to clean the make targets for RPM and container builds, use:
#
#   agent/containers/images/container_build.sh --clean

export PB_AGENT_DISTRO=${PB_AGENT_DISTRO:-fedora-38}
export WORKSPACE_TMP=${WORKSPACE_TMP:-${HOME}}

function usage {
    printf "Build a Pbench Agent container for the distribution named by the\n"
    printf "PB_AGENT_DISTRO environment variable, which defaults to '${PB_AGENT_DISTRO}'.\n"
    printf "\nThe following options are available:\n"
    printf "\n"
    printf -- "\t-c|--clean\n"
    printf "\t\tRemove old RPM and container image targets before building.\n"
    printf -- "\t-h|--help\n"
    printf "\t\tPrint this usage message and terminate.\n"
}

opts=$(getopt -q -o ch --longoptions "clean,help" -n "${0}" -- "${@}")
if [[ ${?} -ne 0 ]]; then
    printf -- "%s %s\n\n\tunrecognized option specified\n\n" "${0}" "${*}" >&2
    usage >&2
    exit 1
fi
eval set -- "${opts}"
rpm_clean=
image_clean=
while true; do
    arg=${1}
    shift
    case "${arg}" in
    -c|--clean)
        rpm_clean=distclean
        image_clean=clean
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

make -C agent/rpm ${rpm_clean} ${PB_AGENT_DISTRO}-rpm
make -C agent/containers/images CI=1 CI_RPM_ROOT=${WORKSPACE_TMP} \
    ${image_clean} ${PB_AGENT_DISTRO}-everything
