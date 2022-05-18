#!/usr/bin/env bash
# Copyright 2018 The MLPerf Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =============================================================================

msg() {
	printf "\n\x1b[0;45m    \x1b[0;1m %s\x1b[m\n" "$*"
}

ci_flake8() {
        # stop the build if there are Python syntax errors or undefined names
	flake8 --count --statistics --extend-exclude lib/external \
		--select=E9,F63,F7,F82 --show-source
        # exit-zero treats all errors as warnings. The GitHub editor is 127 chars wide
	flake8 --count --statistics --extend-exclude lib/external \
		--ignore E203,W503 --exit-zero --max-line-length=127
}

ci_black() {
	black --check --diff --exclude lib/external .
}

ci_mypy() {
	(cd ..; mypy --allow-redefinition --strict --pretty --no-warn-unused-ignores \
		-p ptd_client_server)
}

ci_pytest() {
	(cd ..; python -m pytest ptd_client_server)
}

cd "$(dirname "${BASH_SOURCE[0]}")"

CHECKS="${1-flake8 black mypy pytest}"

FAILED_CHECKS=()

for check in $CHECKS; do
	msg "$check"
	if ! "ci_$check"; then
		FAILED_CHECKS=("${FAILED_CHECKS[@]}" "$check")
	fi
done

if [ "${#FAILED_CHECKS[@]}" = 0 ]; then
	msg $'\x1b[32mAll OK'
else
	msg $'\x1b[31mFailed checks: '"${FAILED_CHECKS[*]}"
	exit 1
fi
