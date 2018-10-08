#! /bin/bash

# force UTC everywhere
export TZ=UTC

if [ -z "$PROG" ]; then
    echo "$(basename $0): ERROR: \$PROG environment variable does not exist." > /dev/stdout
    exit 2
fi
if [ -z "$dir" ]; then
    echo "$(basename $0): ERROR: \$dir environment variable does not exist." > /dev/stdout
    exit 2
fi

function doexit {
    echo "$PROG: $1" >&2
    exit 1
}

# The only directory we verify exists here is $TMP, we leave
# the rest to the individual scripts to check.

# $TOP is generally some distributed file system with lots of space.
# TMP was a subdirectory, but that has caused problems occasionally,
# so we (optionally) make it a local directory now. That decouples the
# immediate availability of data from long-term storage
# considerations.  Not every script does that however: see
# pbench-unpack-tarballs for a script that does this, when called with
# two arguments (if it is called with one, both TOP and TOP_LOCAL are
# set to the same thing).

if which getconf.py > /dev/null 2>&1 ;then
    :
else
    doexit "ERROR: The configtools package must be installed."
fi

# Required
TOP=$(getconf.py pbench-top-dir pbench-files)
test -d $TOP || doexit "Bad TOP=$TOP"

# Required
TMP=$(getconf.py pbench-tmp-dir pbench-files)
test -d $TMP || doexit "Bad TMP=$TMP"

export LOGSDIR=$(getconf.py pbench-logs-dir pbench-files)
test -d $LOGSDIR || doexit "Bad LOGSDIR=$LOGSDIR"

# Optional
BDIR=$(getconf.py pbench-backup-dir pbench-files)
PBENCH_ENV=$(getconf.py pbench-environment results)

if [[ -z "$_PBENCH_SERVER_TEST" ]]; then
    # the real thing

    BINDIR=$(getconf.py script-dir pbench-server)
    LIBDIR=$(getconf.py deploy-lib-dir pbench-server)

    if [[ -z "$BINDIR" ]]; then
        echo "$PROG: ERROR: BINDIR not defined" > /dev/stdout
        exit 3
    fi
    if [[ -z "$LIBDIR" ]]; then
        echo "$PROG: ERROR: LIBDIR not defined" > /dev/stdout
        exit 3
    fi
    # this is used by pbench-report-status
    export IDXCONFIG=$LIBDIR/config/pbench-index.cfg

    function timestamp {
        echo "$(date +'%Y-%m-%dT%H:%M:%S-%Z')"
    }

    function timestamp-seconds-since-epoch {
        echo "$(date +'%s')"
    }

    # Ensure the path where pbench-base.sh was found is in the PATH environment
    # variable.
    export PATH=${dir}/${PATH}
else
    # unit test regime

    # IDXCONFIG (used by pbench-report-status) is exported by the unittests
    # script in this case.

    function timestamp {
        echo "1900-01-01T00:00:00-UTC"
    }

    function timestamp-seconds-since-epoch {
        # 2001/01/01T00:00:00
        echo "978282000"
    }

    # For PATH the unit test environment takes care of the proper setup to
    # ensure everything gets mocked out properly.
fi

ARCHIVE=${TOP}/archive/fs-version-001
INCOMING=${TOP}/public_html/incoming
# this is where the symlink forest is going to go
RESULTS=${TOP}/public_html/results
USERS=${TOP}/public_html/users

# Convenient task run identifier.
if [ "$TS" = "" ]; then
    TS="run-$(timestamp)"
fi

# the scripts may use this to send status messages
export mail_recipients=$(getconf.py mailto pbench-server)

# make all the state directories for the pipeline and any others needed
# every related state directories are paired together with their
# final state at the end
LINKDIRS="TODO BAD-MD5 \
    TO-UNPACK UNPACKED MOVED-UNPACKED  \
    TO-SYNC SYNCED \
    TO-LINK \
    TO-INDEX INDEXED WONT-INDEX \
    TO-COPY-SOS COPIED-SOS \
    TO-BACKUP \
    SATELLITE-MD5-PASSED SATELLITE-MD5-FAILED \
    TO-DELETE SATELLITE-DONE"

# list of the state directories which will be excluded during rsync
EXCLUDE_DIRS="$LINKDIRS WONT-INDEX*"

function mk_dirs {
    hostname=$1

    for d in $LINKDIRS ;do
        thedir=$ARCHIVE/$hostname/$d
        mkdir -p $thedir
        if [[ $? -ne 0 || ! -d "$thedir" ]]; then
            return 1
        fi
    done
    # to accommodate different exit codes from index-pbench
    mkdir -p $ARCHIVE/$hostname/WONT-INDEX.{1..12}
    if [[ $? -ne 0 ]]; then
        return 2
    fi
}

function log_init {
    LOG_DIR=$LOGSDIR/${1}
    mkdir -p $LOG_DIR
    if [[ $? -ne 0 || ! -d "$LOG_DIR" ]]; then
        doexit "Unable to find/create logging directory, $LOG_DIR"
    fi

    log_file=$LOG_DIR/${1}.log
    error_file=$LOG_DIR/${1}.error

    exec 100>&1  # Save stdout on FD 100
    exec 200>&2  # Save stderr on FD 200

    exec 1>>"$log_file"
    exec 2>&1
    exec 4>>"$error_file"
}

function log_finish {
    exec 1>&100  # Restore stdout
    exec 2>&200  # Restore stderr
    exec 100>&-  # Close log file
    exec 4>&-    # Close error file
}

function log_exit {
    echo "$PROG: $1" >&4
    log_finish
    exit 1
}

# Function used by the shims to quarantine problematic tarballs.  It
# is assumed that the function is called within a log_init/log_finish
# context.  Errors here are fatal but we log an error message to help
# diagnose problems.
function quarantine () {
    dest=$1
    shift
    files="$@"

    mkdir -p $dest
    sts=$?
    if [ $sts -ne 0 ] ;then
        # log error
        echo "$TS: quarantine $dest $files: \"mkdir -p $dest\" failed with status $sts" >&4
        log_finish
        exit 101
    fi
    mv $files $dest
    sts=$?
    if [ $sts -ne 0 ] ;then
        # log error
        echo "$TS: quarantine $dest $files: \"mv $files $dest\" failed with status $sts" >&4
        log_finish
        exit 102
    fi
}
