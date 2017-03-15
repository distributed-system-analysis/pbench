#!/bin/bash

if [ "$1" == "" ]; then
    USER=pbench
else
    USER=$1
fi
if [ "$2" == "" ]; then
    HOST=dhcp31-187.perf.lab.eng.bos.redhat.com
else
    HOST="$2"
fi
if [ "$3" == "" ]; then
    PREFIX=/pbench
else
    PREFIX="$3"
fi

# A simplistic deployment script to take the various javascript and css
# files needed on the pbench web site and move them into place, potentially
# removing or updating the existing ones, or adding new ones.

function vdeploy {
    if [ ! -d $(dirname $0)/$1 ]; then
        echo "Can't find local $1 directory tree to deploy"
        exit 1
    fi
    echo "Copying $1/css, $1/js, $1/html, $1/components to $USER@$HOST:$PREFIX/public_html/static/css/$1, /static/js/$1, /static/pages/$1, /static/components/$1"
    ssh $USER@$HOST mkdir -p $PREFIX/public_html/static/css/$1 $PREFIX/public_html/static/js/$1 $PREFIX/public_html/static/pages/$1 $PREFIX/public_html/static/components/$1
    scp -r $(dirname $0)/$1/css/* $USER@$HOST:$PREFIX/public_html/static/css/$1/
    scp -r $(dirname $0)/$1/js/*  $USER@$HOST:$PREFIX/public_html/static/js/$1/
    scp -r $(dirname $0)/$1/pages/* $USER@$HOST:$PREFIX/public_html/static/pages/$1/
    scp -r $(dirname $0)/$1/components/* $USER@$HOST:$PREFIX/public_html/static/components/
}

vdeploy v0.2

echo "Fix up protections"
ssh $USER@$HOST chmod -R g-w $PREFIX/public_html/static

exit 0
