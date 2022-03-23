ROLES = $(wildcard  roles/*)
NROLES = $(shell echo ${ROLES} | wc -w)
README = $(wildcard roles/*/README.md)
NREADME= $(shell echo ${README} | wc -w)


all:	lint check-readme

lint:
	ansible-lint -c ansible-lint.yml
	yaml-lint $$(find . -type f -name '*.yml')

check-readme:
	./check-readmes
