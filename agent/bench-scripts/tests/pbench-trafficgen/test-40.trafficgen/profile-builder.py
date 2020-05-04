#!/bin/bash

if [[ -z "${*}" ]]; then
    echo "${0}" >> ${_testlog}
else
    echo "${0} ${*}" >> ${_testlog}
fi
exit 0
