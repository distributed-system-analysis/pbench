# How to talk to Galaxy
apiserver = https://galaxy.ansible.com/api/
apikey = ${APIKEY}

# Collection info
namespace = pbench
collection = agent
version = $(shell ./bin/yamlconf -C ./pbench/agent/galaxy.yml version)

# Tar ball name and collections directory path
tb = ${namespace}-${collection}-${version}.tar.gz
colldir = collections/ansible_collections/${namespace}/${collection}

build:
	ansible-galaxy collection build ${namespace}/${collection}

test:   build
	ansible-galaxy collection install ${tb} -p ./collections
	git submodule update --init --recursive
	cd ${colldir}; ansible-test sanity

publish: clean build
	ansible-galaxy collection publish -vvv -s "${apiserver}"  --api-key "${apikey}" ${tb}

clean:
	sudo rm -rf collections
	rm -f ${tb} ${namespace}-${collection}-*.tar.gz
