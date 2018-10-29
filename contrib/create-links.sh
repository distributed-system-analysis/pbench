#!/bin/bash

mypwd=`/bin/pwd`
subdir=`basename $mypwd`
if [ "$subdir" != "agent" ]; then
	echo "you need to run this from ./agent dir in a pbench git repo"
	exit 1
fi
for dir in config lib util-scripts bench-scripts bench-scripts/postprocess tool-scripts tool-scripts/postprocess; do
		for i in `find $dir -maxdepth 1 | grep -v gold | grep -v unittests | grep -v samples | grep -v test-bin`; do
		if [ ! -e /opt/pbench-agent/$i ]; then
			echo creating symlink "$mypwd/$i <- /opt/pbench-agent/$i"
			ln -sf $mypwd/$i /opt/pbench-agent/$i
		fi
	done
done
