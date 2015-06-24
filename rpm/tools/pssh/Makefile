prog = pssh
version = 2.3.1
arch = noarch

all: rpm rpm-copy

rpm: all-but-build build

# order matters: spec-copy before pbench-sysstat-tar
all-but-build: check clean remotetar

include ${TOP}/rpm/misc-scripts/mk/rpm.mk
