# install the bg tasks stuff on archive server and set up the crontab
DESTHOST = pbench@example.com

SCRIPTS = pbench-base.sh pbench-unpack-tarballs pbench-copy-sosreports pbench-edit-prefixes pbench-index\
	  pbench-create-results-links pbench-clean-up-dangling-results-links

ALTDESTHOST = pbench@alt.example.com
ALTSCRIPTS = pbench-base.sh pbench-backup-tarballs

all:	scripts altscripts crontab altcrontab index

.PHONY: scripts altscripts crontab altcrontab

scripts:
	cd pbench/bin; rsync -avz ${SCRIPTS} ${DESTHOST}:/home/pbench/bin

altscripts:
	cd pbench/bin; rsync -avz ${ALTSCRIPTS} ${ALTDESTHOST}:/home/pbench/bin

# Install the crontab file.
crontab:
	cd pbench/crontab; rsync -avz crontab.pbench ${DESTHOST}:/home/pbench/crontab
	-ssh ${DESTHOST} crontab /home/pbench/crontab/crontab.pbench

altcrontab:
	cd pbench/crontab; rsync -avz altcrontab.pbench ${ALTDESTHOST}:/home/pbench/crontab
	-ssh ${ALTDESTHOST} crontab /home/pbench/crontab/altcrontab.pbench

ixlib:
	cd pbench/lib; rsync -avz config vos mappings ${DESTHOST}:/home/pbench/lib
	cd pbench; rsync -avz test-data ${DESTHOST}:/home/pbench

index:	ixlib
	cd pbench/bin; rsync -avz index-pbench Makefile ${DESTHOST}:/home/pbench/bin
