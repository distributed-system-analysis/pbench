#!/bin/bash

if [[ -z "${*}" ]]; then
    echo "${0}" >> ${_testlog}
else
    echo "${0} ${*}" >> ${_testlog}
fi

echo "Starting binary-search"
echo "Finished binary-search"
exit 0
