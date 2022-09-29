# DRAFT ...

----

# Hello Pbench!

I'd like to start a discussion about the designs being contemplated for the Pbench Agent 1.0 release.


## Principles

There are a few principles of the designs that we would like to have in place to guide the direction being considered.

"The Pbench Agent ..."

 1. "... is about delivering efficient and comprehensive data & metadata collection."

 2. "... leverages existing tool data collection sub-systems where possible."

 3. "... software dependencies are minimal."

 4. "... offers APIs along side its CLI for accessing its functions and sub-systems."


## Design Changes Being Considered

### One CLI Command: `pbench`

 - Written in Python 3 using `click` to facilitate multiple sub-commands (e.g `pbench results move` instead of `pbench-move-results`)
 - Code base will shed all existing Perl code, and most if not all `bash` code
 - Located at /usr/bin/pbench

Helps reduce sprawl of software dependencies towards principle 3.

### API for Tool Meister Sub-system

 - A documented / published API (Python 3) will be provided for interfacing with the Tool Meister Sub-system of the Pbench Agent

### One CLI Benchmark Command: `pbench benchmark`

 - There will be one CLI interface for driving benchmarks
   - replaces `pbench-user-benchmark`, etc.
   - the existing `bench-scripts` interfaces will be moved to a legacy repo to maintain compatibility
 - This CLI interface will be expanded beyond what `pbench-user-benchmark` offered to facilitate supporting the existing legacy benchmarks (`pbench-fio`, `pbench-uperf`, etc.)
 - The implementation will leverage public APIs for the Tool Meister sub-system

While following principle 4 it also helps us towards principle 1 where the Pbench Agent focuses on  the data and metadata collection and not on running workloads.

### Tool and Benchmark Post-processing Dropped

The Legacy interfaces will provide the existing post-processing functionality, but separate post-processing modules shared with the Pbench Server will be available for use via a separate delivery mechanism.

### Existing Tools Replaced by PCP and/or Prometheus

TBD - Need to list tools map to PCP/Prometheus, and which tools remain (eg. perf record, strace, etc.)

### Tool Meister Sub-System can collect from existing PCP PMCDs and/or Prometheus Exporters


## Table Mapping Existing Interfaces to Proposed

In /opt/pbench-agent/bench-scripts:

 * Removed
   * compare-bench-results
   * pbench-gen-iterations

 * Replaced
   * pbench-user-benchmark --> "pbench benchmark ..."

 * Moved to Legacy Package
   * pbench-fio
   * pbench-linpack
   * pbench-specjbb2005
   * pbench-uperf

In /opt/pbench-agent/utils-scripts:

 * Removed
   * get-internal-tool
   * pbench-add-metalog-option
   * pbench-config
   * pbench-display-sysinfo-options
   * pbench-is-local
   * pbench-kill-tools            --> "via API only"
   * pbench-log-timestamp
   * pbench-make-result-tb        --> "via API only"
   * pbench-output-monitor
   * pbench-postprocess-tools     --> "via API only (maybe?)"
   * pbench-send-tools            --> "via API only"
   * pbench-start-tools           --> "via API only"
   * pbench-stop-tools            --> "via API only"
   * pbench-tool-meister-client   --> "via API only"
   * pbench-tool-meister-start    --> "via API only"
   * pbench-tool-meister-stop     --> "via API only"
   * pbench-tool-trigger          --> "via API only"
   * pbench-verify-sysinfo-options
   * require-rpm
   * validate-hostname
   * validate-ipaddress

 * Replaced
   * pbench-cleanup               --> "pbench cleanup"
   * pbench-clear-results         --> "pbench results clear"
   * pbench-clear-tools           --> "pbench tools clear"
   * pbench-copy-result-tb        --> "pbench results push"
   * pbench-copy-results          --> "pbench resutls copy"
   * pbench-generate-token        --> "pbench token generate"
   * pbench-kill-tools            --> "pbench tools kill"
   * pbench-list-tools            --> "pbench tools list"
   * pbench-list-triggers         --> "pbench tool trigger list"
   * pbench-move-results          --> "pbench resutls move"
   * pbench-register-tool         --> "pbench tools register"
   * pbench-register-tool-set     --> "pbench toolset register
   * pbench-register-tool-trigger --> "pbench tool trigger register"
   * pbench-results-move          --> "pbench resutls move"
   * pbench-results-push          --> "pbench results push"


## Regarding Legacy Interfaces

...