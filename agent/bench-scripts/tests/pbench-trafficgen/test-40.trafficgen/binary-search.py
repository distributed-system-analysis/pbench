#!/bin/bash

if [[ -z "${*}" ]]; then
    echo "${0}" >> ${_testlog}
else
    echo "${0} ${*}" >> ${_testlog}
fi

echo "Starting something other than a binary-search"
echo "Finished something other than a binary-search"
exit 0
