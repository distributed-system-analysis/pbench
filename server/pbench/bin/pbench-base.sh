#! /bin/bash

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
    echo "$PROG: ERROR: The configtools package must be installed." > /dev/stdout
    exit 2
fi

TMP=$(getconf.py pbench-tmp-dir pbench-files)
PBENCH_ENV=$(getconf.py pbench-environment results)

test -d $TMP || doexit "Bad TMP=$TMP"

TOP=$(getconf.py pbench-top-dir pbench-files)
BDIR=$(getconf.py pbench-backup-dir pbench-files)
LOGSDIR=$(getconf.py pbench-logs-dir pbench-files)

ARCHIVE=${TOP}/archive/fs-version-001
INCOMING=${TOP}/public_html/incoming
# this is where the symlink forest is going to go
RESULTS=${TOP}/public_html/results


if [[ -z "$_PBENCH_SERVER_TEST" ]]; then
    function timestamp {
        echo "$(date +'%Y-%m-%dT%H:%M:%S-%Z')"
    }
    function timestamp-seconds-since-epoch {
        echo "$(date +'%s')"
    }
else
    function timestamp {
        echo "1900-01-01T00:00:00-UTC"
    }
    function timestamp-seconds-since-epoch {
        # 2001/01/01T00:00:00
        echo "978282000"
    }
fi

# Convenient task run identifier.
if [ "$TS" = "" ]; then
    TS="run-$(timestamp)"
fi

# all the scripts use this to send status messages
mail_recipients=$(getconf.py mailto pbench-server)

# make all the state directories for the pipeline and any others needed
LINKDIRS="TODO TO-COPY-SOS TO-INDEX INDEXED WONT-INDEX DONE BAD-MD5"

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
