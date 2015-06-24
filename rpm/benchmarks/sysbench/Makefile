prog = sysbench
version = 0.4.12
arch = x86_64

all: rpm rpm-copy

rpm: all-but-build build 

all-but-build: check clean remotetar

include ${TOP}/rpm/misc-scripts/mk/rpm.mk
