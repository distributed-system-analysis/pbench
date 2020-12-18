_prefix="${1}"

pip3 install --no-cache-dir --prefix="${_prefix}" -r ${progdir}/lint-requirements.txt -r ${progdir}/agent/requirements.txt -r ${progdir}/server/requirements.txt -r ${progdir}/agent/test-requirements.txt -r ${progdir}/server/test-requirements.txt

_pdir=${_prefix}/bin
if [[ ":${PATH:-}:" != *":${_pdir}:"* ]]; then
    export PATH=${_pdir}${PATH:+:${PATH}}
fi

NL=$'\n'
while read -r _pdir; do
    if [[ ":${PYTHONPATH:-}:" != *":${_pdir}:"* ]]; then
        PYTHONPATH=${_pdir}${PYTHONPATH:+:${PYTHONPATH}}
    fi
done <<< "$(ls -1d ${_prefix}/lib*/python3.*/site-packages 2> /dev/null)${NL}$(head -n 1 ${_prefix}/lib*/python3.*/site-packages/pbench.egg-link 2> /dev/null)"
export PYTHONPATH
