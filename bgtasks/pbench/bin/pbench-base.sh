#! /bin/bash

function doexit {
    echo "$PROG: $1" >&2
    exit 1
}

if [[ -z "$TOP" ]]; then
    doexit "TOP not defined before sourcing"
fi

# The only directory we verify exists here is $TMP, we leave
# the rest to the individual scripts to check.
TMP=$TOP/tmp
test -d $TMP || doexit "Bad TMP=$TMP"

ARCHIVE=$TOP/archive/fs-version-001
LOGSDIR=$TOP/logs
INCOMING=$TOP/public_html/incoming
# this is where the symlink forest is going to go
RESULTS=$TOP/public_html/results

if [[ -z "$_PBENCH_BGTASKS_TEST" ]]; then
    function timestamp {
        echo "$(date +'%Y-%m-%dT%H:%M:%S-%Z')"
    }
else
    function timestamp {
        echo "1900-01-01T00:00:00-UTC"
    }
fi

# Convenient task run identifier.
if [ "$TS" = "" ]; then
    TS="run-$(timestamp)"
fi

mail_recipients=$(getconf.py mailto mail)

# make all the state directories for the pipeline and any others needed
function mk_dirs {
    hostname=$1

    mkdir -p $ARCHIVE/$hostname/{TODO,TO-COPY-SOS,TO-INDEX,INDEXED,WONT-INDEX,DONE} $TMP/$hostname $INCOMING/$hostname
}

function log_init {
    LOG_DIR=$LOGSDIR/$(basename $0)
    mkdir -p $LOG_DIR
    if [[ $? -ne 0 || ! -d "$LOG_DIR" ]]; then
        doexit "Unable to find/create logging directory, $LOG_DIR"
    fi

    log_file=$LOG_DIR/$1.log
    error_file=$LOG_DIR/$1.error

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
