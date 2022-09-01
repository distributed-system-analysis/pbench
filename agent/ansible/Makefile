# How to talk to Galaxy
apiserver = https://galaxy.ansible.com/api/
apikey = ${APIKEY}

namespace = pbench
collection = agent
version = $(shell ./bin/yamlconf -C ./galaxy.yml version)

# Tar ball name and collections directory path
tb = ${namespace}-${collection}-${version}.tar.gz
colldir = collections/ansible_collections/${namespace}/${collection}

.DEFAULT_GOAL := test

lint:
	ansible-lint -c ansible-lint.yml
	yaml-lint $$(find . -type f -name '*.yml')
	bin/check-readmes

build:	lint
	ansible-galaxy collection build

test:   build
	ansible-galaxy collection install ${tb} -p ./collections
	git submodule update --init --recursive
	cd ${colldir}; ansible-test sanity

publish: clean build
	ansible-galaxy collection publish -vvv -s "${apiserver}"  --api-key "${apikey}" ${tb}

clean:
	rm -rf collections
	rm -f ${tb} ${namespace}-${collection}-*.tar.gz
