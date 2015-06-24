#!/bin/bash

dev=/dev/ram0
clear-results
clear-tools
register-tool --name=mpstat -- --interval=2
register-tool --name=perf -- --record-opts="record -a -g"
register-tool --name=pidstat -- --interval=2
if mount | grep -q "$dev"; then
	echo "unmounting $dev"
	umount $dev
fi
# fio --config=ramdisk-block --test-types=randwrite --targets=$dev --block-sizes=4 --ioengine=libaio --runtime=60
fio --config=ramdisk-block-pvsync --test-types=randwrite --targets=$dev,$dev,$dev,$dev,$dev,$dev,$dev,$dev,$dev,$dev,$dev,$dev,$dev,$dev,$dev,$dev,$dev,$dev,$dev,$dev,$dev,$dev,$dev,$dev,$dev,$dev,$dev,$dev,$dev,$dev,$dev,$dev --block-sizes=4 --ioengine=pvsync --runtime=60
