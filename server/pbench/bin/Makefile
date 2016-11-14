UTEST =
UTIME =
TB = uperf__2016-10-06_16:34:03.tar.xz
TB = uperf__2016-10-12_16:31:34.tar.xz

# on perf42
dir=/home/pbench/testing
# on alphaville
dir=/home/nick/src/github/pbench/worktrees/wip-indexing/server/pbench

run:
	bash -c '\
	export CONFIG=${dir}/lib/config/pbench-server.cfg.example;\
	. ${dir}/bin/pbench-base.sh; \
	export TMPDIR=$$TMP/pbench-index.$$$$; \
	mkdir -p $$TMPDIR; \
	./es/es-index-create 10; \
	./es/es-settings start > settings.json; \
	time PYTHONPATH=${dir}/lib:$$PYTHONPATH python3 index-pbench ${UTEST} ${UTIME} -C ${dir}/lib/config/pbench-index.cfg.example ${dir}/bin/state/tmp/${TB}; \
	./es/es-settings end >> settings.json'


test:
	bash -c '\
	export CONFIG=${dir}/lib/config/pbench-server.cfg.example;\
	. ${dir}/bin/pbench-base.sh; \
	export TMPDIR=$$TMP/pbench-index.$$$$; \
	mkdir -p $$TMPDIR; \
	bash -x ./es-set-throttle-type merge'

clean:
	./es/es-index-delete 10

create:
	./es/es-index-create 10

