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
else
    # Ensure the configuration file in play is self-consistent with the
    # location from which this script is being invoked.
    BINDIR=$(getconf.py script-dir pbench-server)
    if [ "$BINDIR" != "$dir" ]; then
        echo "$PROG: ERROR: BINDIR (\"$BINDIR\") not defined as \"$dir\"" > /dev/stdout
        exit 3
    fi
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
TOP=$(getconf.py pbench-top-dir pbench-server)
test -d $TOP || doexit "Bad TOP=$TOP"

# Required
TMP=$(getconf.py pbench-tmp-dir pbench-server)
test -d $TMP || doexit "Bad TMP=$TMP"

# Required
export LOGSDIR=$(getconf.py pbench-logs-dir pbench-server)
test -d $LOGSDIR || doexit "Bad LOGSDIR=$LOGSDIR"

# Optional
PBENCH_ENV=$(getconf.py environment pbench-server)

# Ensure the path where pbench-base.sh was found is in the PATH environment
# variable.
if [[ ! ":$PATH:" =~ ":${dir}:" ]]; then
   PATH=${dir}${PATH:+:}$PATH; export PATH
fi

if [[ -z "$_PBENCH_SERVER_TEST" ]]; then
    # the real thing

    LIBDIR=$(getconf.py lib-dir pbench-server)
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

    function get-tempdir-name {
        # make the names reproducible for unit tests
        echo "$TMP/${1}.$$"
    }
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

    function get-tempdir-name {
        # make the names reproducible for unit tests
        echo "$TMP/${1}.XXXXX"
    }
fi

ARCHIVE=$(getconf.py pbench-archive-dir pbench-server)
INCOMING=$(getconf.py pbench-incoming-dir pbench-server)
# this is where the symlink forest is going to go
RESULTS=$(getconf.py pbench-results-dir pbench-server)
USERS=$(getconf.py pbench-users-dir pbench-server)

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
EXCLUDE_DIRS="_QUARANTINED $LINKDIRS $(for i in {1..11}; do printf 'WONT-INDEX.%d ' ${i}; done)"

function mk_dirs {
    hostname=$1

    for d in $LINKDIRS ;do
        thedir=$ARCHIVE/$hostname/$d
        mkdir -p $thedir
        if [[ $? -ne 0 || ! -d "$thedir" ]]; then
            return 1
        fi
    done
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

    mkdir -p $dest > /dev/null 2>&1
    sts=$?
    if [ $sts -ne 0 ] ;then
        # log error
        echo "$TS: quarantine $dest $files: \"mkdir -p $dest/\" failed with status $sts" >&4
        log_finish
        exit 101
    fi
    for afile in ${files} ;do
        if [ ! -e $afile -a ! -L $afile ] ;then
            continue
        fi
        mv $afile $dest/ > /dev/null 2>&1
        sts=$?
        if [ $sts -ne 0 ] ;then
            # log error
            echo "$TS: quarantine $dest $files: \"mv $afile $dest/\" failed with status $sts" >&4
            log_finish
            exit 102
        fi
    done
}
