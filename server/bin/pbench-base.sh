#! /bin/bash

# Helper functions for pbench-server bash scripts.  All environment variables
# are defined in pbench-base.py which execv()'d our caller.

if [[ -z "${PROG}" ]]; then
    echo "$(basename ${0}): ERROR: \${PROG} environment variable does not exist." > /dev/stdout
    exit 2
fi
if [[ -z "${dir}" ]]; then
    echo "$(basename ${0}): ERROR: \${dir} environment variable does not exist." > /dev/stdout
    exit 3
else
    # Ensure the configuration file in play is self-consistent with the
    # location from which this script is being invoked.
    if [[ "${BINDIR}" != "${dir}" ]]; then
        echo "${PROG}: ERROR: BINDIR (\"${BINDIR}\") not defined as \"${dir}\"" > /dev/stdout
        exit 4
    fi
    # Ensure the path where pbench-base.sh was found is in the PATH environment
    # variable.
    if [[ ! ":${PATH}:" =~ ":${BINDIR}:" ]]; then
        echo "${PROG}: ERROR: BINDIR (\"${BINDIR}\") not in PATH=\"${PATH}\"" > /dev/stdout
        exit 5
    fi
fi

function doexit {
    echo "${PROG}: ${1}" >&2
    exit 1
}

if [[ -z "${_PBENCH_SERVER_TEST}" ]]; then
    # the real thing

    function timestamp {
        echo "$(date +'%Y-%m-%dT%H:%M:%S-%Z')"
    }

    function timestamp-seconds-since-epoch {
        echo "$(date +'%s')"
    }

    function get-tempdir-name {
        # make the names reproducible for unit tests
        echo "${TMP}/${1}.${$}"
    }
else
    # unit test regime

    function timestamp {
        echo "1970-01-01T00:00:42-UTC"
    }

    function timestamp-seconds-since-epoch {
        # 1970-01-01T00:00:42-UTC
        echo "42"
    }

    function get-tempdir-name {
        # make the names reproducible for unit tests
        echo "${TMP}/${1}.XXXXX"
    }
fi

function log_init {
    local _LOG_DIR=${LOGSDIR}/${1}
    mkdir -p ${_LOG_DIR}
    if [[ ${?} -ne 0 || ! -d "${_LOG_DIR}" ]]; then
        doexit "Unable to find/create logging directory, ${_LOG_DIR}"
    fi

    local _log_file=${_LOG_DIR}/${1}.log
    local _error_file=${_LOG_DIR}/${1}.error

    exec 100>&1  # Save stdout on FD 100
    exec 200>&2  # Save stderr on FD 200

    exec 1>>"${_log_file}"
    exec 2>&1
    exec 4>>"${_error_file}"
}

function log_finish {
    exec 1>&100-  # Restore stdout and close log file
    exec 2>&200-  # Restore stderr and close saved stderr
    exec 4>&-     # Close error file
}

function log_exit {
    local _msg="${PROG}: ${1}"
    printf -- "%s\n" "${_msg}" >&4
    logger -t ${PROG} -p daemon.err -- "${1}"
    log_finish
    if [[ -z "${2}" ]]; then
        exit 1
    else
        exit ${2}
    fi
}

function log_debug {
    printf -- "%b\n" "${1}"
    logger -t ${PROG} -p daemon.debug -- "${1}"
}

function log_info {
    printf -- "%b\n" "${1}"
    logger -t ${PROG} -p daemon.info -- "${1}"
}

function log_warn {
    printf -- "%b\n" "${1}"
    logger -t ${PROG} -p daemon.warning -- "${1}"
}

function log_error {
    printf -- "%b\n" "${1}" >&4
    logger -t ${PROG} -p daemon.err -- "${1}"
}
