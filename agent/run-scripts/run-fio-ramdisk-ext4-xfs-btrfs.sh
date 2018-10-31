#!/bin/bash


# This test simulates what happens when a single VM does a multi-threaded random write to a single disk when that VM was configured with "io=threads".
# Fio is used to have several threads write to a single file with pvsync (instead of something like aio call).
# This test is run on a filesystem built on /dev/ram0, using ext4, xfs, and btrfs

dev=/dev/ram0
rmmod brd
modprobe brd rd_size=16777216 rd_nr=1

clear-results
clear-tools
register-tool --name=mpstat -- --interval=2
register-tool --name=perf --
register-tool --name=pidstat -- --interval=2
for fs in ext4 xfs btrfs; do
	if mount | grep -q "$dev"; then
		echo "unmounting $dev"
		umount $dev
	fi
	dd if=/dev/zero of=$dev bs=1M count=1
	mkfs -t $fs $dev
	mkdir -p /mnt/fio
	mount $dev /mnt/fio
	fio --config=ramdisk-$fs --test-types=randwrite --targets=/mnt/fio/file1,/mnt/fio/file1,/mnt/fio/file1,/mnt/fio/file1,/mnt/fio/file1,/mnt/fio/file1,/mnt/fio/file1,/mnt/fio/file1,/mnt/fio/file1,/mnt/fio/file1,/mnt/fio/file1,/mnt/fio/file1  --block-sizes=4 --ioengine=pvsync --runtime=60
	umount $dev
done
move-results
