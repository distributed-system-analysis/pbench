#!/bin/bash

dev=/dev/ram0
clear-results
clear-tools
register-tool --name=lockstat
register-tool --name=mpstat -- --interval=2
register-tool --name=perf -- --record-opts="record -a -g"
register-tool --name=pidstat -- --interval=2
for fs in ext4 xfs btrfs; do
	if mount | grep -q "$dev"; then
		echo "unmounting $dev"
		umount $dev
	fi
	dd if=/dev/zero of=$dev bs=1M count=1
	mkfs.$fs $dev
	mkdir -p /mnt/fio
	mount $dev /mnt/fio
	fio --config=ramdisk-$fs --test-types=randwrite --targets=/mnt/fio/file1,/mnt/fio/file1,/mnt/fio/file1,/mnt/fio/file1,/mnt/fio/file1,/mnt/fio/file1,/mnt/fio/file1,/mnt/fio/file1,/mnt/fio/file1,/mnt/fio/file1,/mnt/fio/file1,/mnt/fio/file1  --block-sizes=4 --ioengine=pvsync --runtime=60
	umount $dev
done
copy-results
