_prefix="${1}"

if [[ -z "${_prefix}" ]]; then
    printf -- "Missing prefix argument!" >&2
    exit 1
fi

pip3 install --no-cache-dir --progress-bar off --no-color --prefix="${_prefix}" -r ${progdir}/lint-requirements.txt -r ${progdir}/docs/requirements.txt -r ${progdir}/agent/requirements.txt -r ${progdir}/server/requirements.txt -r ${progdir}/agent/test-requirements.txt -r ${progdir}/server/test-requirements.txt

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

python3 setup.py develop --prefix="${_prefix}"
