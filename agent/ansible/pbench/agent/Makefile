all:	lint check-readme

lint:
	ansible-lint -c ansible-lint.yml
	yaml-lint $$(find . -type f -name '*.yml')

check-readme:
	./check-readmes
