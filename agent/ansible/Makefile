# How to talk to Galaxy
apiserver = https://galaxy.ansible.com/api/
apikey = ${APIKEY}

namespace = pbench
collection = agent
version = $(shell bin/yamlconf -C collection/galaxy.yml version)

tmpdir = /var/tmp/agent-ansible

# Tar ball name and collections directory path
tb = ${namespace}-${collection}-${version}.tar.gz
colldir = ${tmpdir}/build/ansible_collections/${namespace}/${collection}

.DEFAULT_GOAL := test

lint:
	cd collection; ansible-lint -c ../ansible-lint.yml
	yaml-lint $$(find . -type f -name '*.yml')
	cd collection; ../bin/check-readmes

build:	lint
	mkdir -p ${tmpdir}
	ansible-galaxy collection build --output-path ${tmpdir} --force collection

test:   build
	ansible-galaxy collection install --force ${tmpdir}/${tb} -p ${tmpdir}/build
	cd ${colldir}; ansible-test sanity

publish: clean build
	ansible-galaxy collection publish -vvv -s "${apiserver}"  --api-key "${apikey}" ${tmpdir}/${tb}

clean:
	rm -rf ${tmpdir}
