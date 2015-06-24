prog = linpack
version = 11.1.3
arch = x86_64
# this turns the RPATH complaints from errors to warnings.
QA_RPATHS = $$[ 0x0002 ]

all: rpm rpm-copy

rpm: all-but-build build 

all-but-build: check clean remotetar

include ${TOP}/rpm/misc-scripts/mk/rpm.mk
