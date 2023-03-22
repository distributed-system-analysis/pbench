#
# A Makefile for building the Pbench Dashboard deployment for use in Pbench
# Server functional test and Staging/Production deployments.
#
# This makefile defines the following targets:
#
#  all (the default):  runs lint and unit tests and then builds
#                      the Pbench Dashboard deployment
#  build:              builds the Pbench Dashboard deployment
#  clean:              removes the artifacts created by the other targets
#  run_lint:           runs the Javascript linter
#  run_unittests:      runs the Dashboard unit tests
#

# This is the list of all the subdirectories of the `dashboard` directory which
# contain "source" files for the Dashboard (Javascript, images, style sheets,
# HTML, et al.) -- anything which, if changed, should prompt a new build -- and
# the corresponding list of those files.
SRCDIRS := public src
FILES := $(shell find ${SRCDIRS} -type f)

all: run_lint run_unittests build

build:  package-lock.json node_modules ${FILES}
	mkdir -p build
	npm run build

run_lint:  package-lock.json node_modules
	npx eslint --max-warnings 0 "src/**"
	npx prettier --check "src/**"

run_unittests:  package-lock.json node_modules
	CI=true npm test

package-lock.json node_modules &: ${HOME}/.config package.json
	npm install

${HOME}/.config:
	mkdir -p ${HOME}/.config

clean:
	rm -rf package-lock.json node_modules build

.PHONY: all clean run_lint run_unittests
