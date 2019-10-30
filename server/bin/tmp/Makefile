PYTHONPATH=../../lib:.

IMPL = orig ujson str siss sfss rfss rfsb

all:	rfsb
# all:    ${IMPL}

${IMPL}:
	cd ../../lib/pbench; ln -sf indexer.py.$@ indexer.py
	PYTHONPATH=${PYTHONPATH} ./indexer-driver.py > duration.$@
	PYTHONPATH=${PYTHONPATH} py-spy record --output fg.$@.svg ./indexer-driver.py
