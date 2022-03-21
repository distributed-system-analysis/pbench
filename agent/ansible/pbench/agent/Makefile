ROLES = $(wildcard  roles/*)
NROLES = $(shell echo ${ROLES} | wc -w)
README = $(wildcard roles/*/README.md)
NREADME= $(shell echo ${README} | wc -w)


all:	lint check-readme

lint:
	ansible-lint -c ansible-lint.yml
	yaml-lint $$(find . -type f -name '*.yml')

check-readme:
	@if [ ${NROLES} != ${NREADME} ] ;then\
		echo "Mismatch between roles and README.md files";\
		echo "roles: ${ROLES}";\
	     	echo "role README files: ${README}";\
		exit 1\
	;fi
	if [ ! -f ./README.md ] ;then exit 1 ;fi
	if [ ! -f ./plugins/README.md ] ;then exit 1 ;fi
