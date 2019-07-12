#!/usr/bin/env python3
# -*- mode: python -*-

"""Pbench indexing driver, responsible for indexing a single pbench tar ball
into the configured Elasticsearch V1 instance.

"""

from __future__ import print_function

import sys, os, re, stat, copy, time
import hashlib, json, glob, csv, tarfile, shutil
import configtools, traceback, socket, tempfile

from operator import itemgetter
from datetime import datetime, timedelta
from collections import Counter
from argparse import ArgumentParser
from configparser import ConfigParser, Error as ConfigParserError, \
        NoSectionError, NoOptionError

from pbench import tstos, get_es, es_index, es_put_template, PbenchConfig, \
        BadConfig, get_pbench_logger, quarantine, JsonFileError, \
        PbenchTemplates, TemplateError, report_status, _rename_tb_link


_NAME_ = "pbench-index"

# This is the version of this python code. We use the version number to mean
# the following:
#   <major>.<minor>.<patch>
#     major: change when:
#       - moving between supported versions of Elasticsearch
#       - incompatible changes occur with index name structure
#       - when structure of index mappings change
#     minor: change when:
#       - code structure is changed
#       - additional indexes are added without changing existing indices or
#         mappings
#     patch: change when:
#       - bug fixes are made to existing code that don't affect indices or
#         mappings
# We add the version to the run documents we generate.  Having the version
# number in each run document helps us track down the version of the code that
# generated those documents.  In turn, this can help us fix indexing problems
# via re-indexing data with transformations based on the version of the code
# that generated the documents.
_VERSION_ = "1.0.0"

# Internal debugging flag.
_DEBUG = 0

# global - defaults to normal dict, ordered dict for unittests
_dict_const = dict

# All indexing uses "create" (instead of "index") to avoid updating
# existing records, allowing us to detect duplicates.
_op_type = "create"

# UID keyword pattern
uid_keyword_pat = re.compile("%\w*?%")

# The link source and destination for this operation of this script.
_linksrc = "TO-INDEX"
_linkdest = "INDEXED"
_linkerrdest = "WONT-INDEX"

# ^$!@!#%# compatibility
# FileNotFoundError is python 3.3 and the travis-ci hosts still (2015-10-01) run
# python 3.2
_filenotfounderror = getattr(__builtins__, 'FileNotFoundError', IOError)


class BadDate(Exception):
    pass


class ConfigFileNotSpecified(Exception):
    pass


class ConfigFileError(Exception):
    pass


class BadMDLogFormat(Exception):
    pass


class UnsupportedTarballFormat(Exception):
    pass


class SosreportHostname(Exception):
    pass


_ts_start = None
def _ts(msg, newline=False):
    """Debugging helper for emitting a timestamp aiding timing.
    """
    global _ts_start

    now = datetime.utcnow()
    if _ts_start:
        print(now - _ts_start, file=sys.stderr)
    _ts_start = now
    if newline:
        print(msg, file=sys.stderr)
        _ts_start = None
    else:
        print(msg, end=' ', file=sys.stderr)
    sys.stderr.flush()

def _make_source_id(source, _parent=None):
    the_bytes = json.dumps(source, sort_keys=True).encode('utf-8')
    if _parent is not None:
        the_bytes += str(_parent).encode('utf-8')
    return hashlib.md5(the_bytes).hexdigest()


class PbenchData(object):
    """Pbench Data abstract class - ToolData and ResultData inherit from it.
    """
    def __init__(self, ptb, idxctx):
        self.year, self.month, self.day = (
                "{:04d}".format(ptb.start_run_ts.year),
                "{:02d}".format(ptb.start_run_ts.month),
                "{:02d}".format(ptb.start_run_ts.day))
        self.ptb = ptb
        self.logger = idxctx.logger
        self.idxctx = idxctx
        self.run_metadata = _dict_const([
            ( 'id', ptb.run_metadata['id'] ),
            ( 'controller', ptb.run_metadata['controller'] ),
            ( 'name', ptb.run_metadata['name'] ),
            ( 'script', ptb.run_metadata['script'] ),
            ( 'date', ptb.run_metadata['date'] ),
            ( 'start', ptb.run_metadata['start'] ),
            ( 'end', ptb.run_metadata['end'] ),
        ])
        try:
            self.run_metadata['config'] = ptb.run_metadata['config']
        except KeyError:
            pass
        try:
            self.run_metadata['user'] = ptb.run_metadata['user']
        except KeyError:
            pass
        self.counters = Counter()

    def mk_abs_timestamp_millis(self, orig_ts):
        """Convert the given millis since the epoch relative or absolute
           timestamp to an absolute ISO string timestamp, converting from
           relative to absolute if necessary.

           It is assumed the given timestamp is a float in milliseconds since
           the epoch and is in UTC.
        """
        try:
            orig_ts_float = float(orig_ts)
        except Exception as e:
            self.counters['ts_not_epoch_millis_float'] += 1
            raise BadDate("{!r} is not a float in milliseconds since the"
                    " epoch: {}".format(orig_ts, e))
        ts_float = orig_ts_float/1000
        try:
            ts = datetime.utcfromtimestamp(ts_float)
        except Exception as e:
            self.counters['ts_not_epoch_float'] += 1
            raise BadDate("{:f} ({!r}) is not a proper float in seconds since"
                    " the epoch: {}".format(ts_float, orig_ts, e))
        if ts < self.ptb.start_run_ts:
            # The calculated timestamp, `ts`, is earlier that the timestamp of
            # the start of the pbench run itself, `start_run_ts`.  That can
            # occur because of at least 3 different situations: 1. the
            # recorded start run timestamp, `start_run_ts`, is not correct;
            # 2. the `ts` is a valid absolute timestamp that was incorrectly
            # recorded; 3. the `ts` is a valid _relative_ timestamp, measured
            # from the beginning of some unknown time `T0`.
            #
            # Since we do not have enough information at this point to correct
            # or detect the 1st or 2nd situation, we make an attempt to detect
            # and correct the 3rd situation.
            #
            # For the 3rd situation, we make an attempt to treat the original
            # timestamp as if it is relative to the start of the run, and
            # calculate a _new_ absolute timestamp from that point.  If that
            # new absolute timestamp is before the end of the run as well, we
            # just use the new absolute timestamp instead of the relative
            # timestamp.  If the new absolute timestamp is beyond the end of
            # the run, it is likely that the timestamp is not relative so we
            # raise an error.
            try:
                d = timedelta(0, 0, orig_ts_float * 1000)
            except Exception as e:
                self.counters['ts_calc_not_epoch_millis_float'] += 1
                raise BadDate("{:f} ({!r}) is not a proper float in"
                        " milliseconds since the epoch: {}".format(
                            orig_ts_float, orig_ts, e))
            newts = self.ptb.start_run_ts + d
            if newts > self.ptb.end_run_ts:
                self.counters['ts_before_start_run_ts'] += 1
                raise BadDate("{} ({!r}) is before the start of the"
                        " run ({})".format(ts, orig_ts, self.ptb.start_run_ts))
            else:
                ts = newts
        elif ts > self.ptb.end_run_ts:
            self.counters['ts_after_end_run_ts'] += 1
            raise BadDate("{} ({!r}) is after the end of the"
                    " run ({})".format(ts, orig_ts, self.ptb.end_run_ts))
        return ts.strftime("%Y-%m-%dT%H:%M:%S.%f")

    def generate_index_name(self, template_name, source, toolname=None):
        """Return a fully formed index name given its template, prefix, source
        data (for an @timestamp field) and an optional tool name."""
        try:
            template = self.idxctx.templates.index_patterns[template_name]['template']
            idxname_tmpl = self.idxctx.templates.index_patterns[template_name]['idxname']
        except KeyError as e:
            raise Exception("Invalid template name, '{}': {}".format(
                template_name, e))
        if toolname is not None:
            idxname = idxname_tmpl.format(tool=toolname)
            try:
                version = self.idxctx.templates.versions[idxname]
            except KeyError as e:
                raise Exception("Invalid tool index name for version, '{}':"
                    " {}".format(idxname, e))
        else:
            idxname = idxname_tmpl
            try:
                version = self.idxctx.templates.versions[template_name]
            except KeyError as e:
                raise Exception("Invalid index template name for version,"
                    " '{}': {}".format(idxname, e))
        try:
            ts_val = source['@timestamp']
        except KeyError:
            self.counters['ts_missing_at_timestamp'] += 1
            raise BadDate("missing @timestamp in a source document:"
                    " {!r}".format(source))
        except TypeError as e:
            raise Exception("Failed to generate index name, {!r}, source:"
                    " {!r}".format(e, source))
        year, month, day = source['@timestamp'].split('T', 1)[0].split('-')[0:3]
        if (year, month, day) < (self.year, self.month, self.day):
            raise BadDate("TS y/m/d, {!r}, earlier than pbench run, {!r}".format(
                    (year, month, day), (self.year, self.month, self.day)))
        return template.format(prefix=self.idxctx.idx_prefix, version=version,
                idxname=idxname, year=year, month=month, day=day)


###########################################################################
#

class ResultData(PbenchData):
    """Benchmark result data: JSON files only.

    Each pbench tar ball contains the result of running a benchmark (pbench-*
    bench script or pbench-user-benchmark script wrapping a user provided
    script), where N iterations of that benchmark were run, with each
    iteration having M samples.

    The bench scripts create a result.json file in each sample directory, a
    roll-up of all sample result.json files in the iteration directory's
    result.json for those samples (with the mean, stddev, and closest sample
    calculated, and including all the sample data), and finally a single
    result.json file recording all the iterations run, including all samples
    from all iterations.
    """
    def __init__(self, ptb, idxctx):
        super().__init__(ptb, idxctx)

        self.idxctx.opctx.append(
            _dict_const(object="ResultData", counters=self.counters))
        self.json_dirs = None
        try:
            self.json_dirs = ResultData.get_result_json_dirs(ptb)
        except KeyError:
            self.json_dirs = None

    @staticmethod
    def get_result_json_dirs(ptb):
        """
        Fetch the list of directories containing result.json files for this
        experiment; return a list directory path names.
        """
        paths = [x for x in ptb.tb.getnames() if (os.path.basename(x) == "result.json") and ptb.tb.getmember(x).isfile()]
        dirnames = []
        for p in paths:
            dirnames.append(os.path.dirname(p))
        return dirnames

    def make_source(self):
        """
        If we ever decide we need to process anything other than JSON files, this
        is going to become a jump method, similar to ToolData.make_source().
        ATM, we only handle JSON files.
        """
        if not self.json_dirs:
            # If we do not have any json files for this experiment, ignore it.
            return None
        gen = self._make_source_json()
        return gen

    # Table of data for supported benchmarks and what to look for in the
    # results JSON for "sub-lists" of reported data.
    #
    # Latency results include a latency['usec'] list (or
    # latency['clat'|'slat'|???] in the fio case) *and* a
    # throughput['trans_sec'] list (or throughput['iops_sec'] in the fio
    # case). Each list has elements for "all" and for each client/server pair
    # (or client?) used in the test.
    #
    # Throughput results include a trans_sec, Gb_sec or iops_sec list only,
    # depending on the benchmark (uperf or fio) and the kind of iteration:
    # latency measurements include a trans_sec throughput sublist, but
    # throughput measurements include a GB_sec sublist (for uperf) or an
    # iops_sec sublist (for fio).
    _benchmarks = {
        'uperf': {
            'latency': ['usec'],
            'throughput': ['trans_sec', 'Gb_sec']
        },
        "fio": {
            'latency': ['clat', 'lat', 'slat'],
            'throughput': ['iops_sec']
        },
        "trafficgen": {
        },
        "moongen": {
        },
        "user-benchmark": {
        }
    }

    def _make_source_json(self):
        """Generate source documents for all result.json files we need to
        handle in the list of directories with JSON files, "json_dirs".

        There are three "levels" of result.json files generated by the
        pbench-agent benchmark post-processing code: "sample", "iteration",
        and top-level "summary".  There is one "sample" result.json file
        per sample, with N samples per iteration, and M iterations per
        top-level result.

        The data in an "iteration" result.json file contains an exact copy
        of all "sample" result.json files for that iteration.  The top-level
        result.json contains an exact copy of all the "iteration" result.json
        data.

        We only process the top-level result.json file since it has all the
        data we need in one place.
        """
        for dirname in self.json_dirs:
            if dirname.startswith('sample'):
                # sample result.json - we ignore each sample result.json since
                # each sample is contained in the experiment level
                # result.json.
                continue
            elif dirname != self.ptb.dirname:
                # iteration result.json - there is no value in processing the
                # result.json file at the iteration level because everything
                # it contains is also in the experiment level's result.json.
                continue

            result_json = os.path.join(
                    self.ptb.extracted_root, dirname, "result.json")
            try:
                # Read the file and interpret it as a JSON document.
                with open(result_json) as fp:
                    results = json.load(fp)
            except Exception as e:
                self.logger.warning("result-data-indexing: encountered invalid"
                        " JSON file, {}: {:r}", result_json, e)
                self.counters['not_valid_json_file'] += 1
                continue

            # The outer results object shoul be an array of iterations. Probe
            # to see if that is true.
            if not isinstance(results, list):
                self.logger.warning("result-data-indexing: encountered unexpected"
                        " JSON file format, %s" % (result_json,))
                self.counters['unexpected_json_file_format'] += 1
                continue

            for iteration in results:
                try:
                    iter_number = iteration['iteration_number']
                    iter_name = iteration['iteration_name']
                    iter_data = iteration['iteration_data']
                except Exception:
                    self.logger.warning("result-data-indexing: could not find"
                            " iteration data in JSON file, {}", result_json)
                    self.counters['missing_iteration'] += 1
                    continue
                # Validate the iteration name by looking for the iteration
                # directory on disk.
                iter_dir = os.path.join(
                        self.ptb.extracted_root, dirname, iter_name)
                if not os.path.isdir(iter_dir):
                    iter_name = "{:d}-{}".format(iter_number, iter_name)
                    iter_dir = os.path.join(
                            self.ptb.extracted_root, dirname, iter_name)
                    if not os.path.isdir(iter_dir):
                        self.logger.warning("result-data-indexing: encountered bad"
                                " iteration name '{}' in JSON file, {}",
                                iteration['iteration_name'], result_json)
                        self.counters['bad_iteration_name'] += 1
                        continue
                # Generate JSON documents for each iteration using the
                # iteration metadata name and number.
                for src, _id, _parent, _type in self._handle_iteration(
                        iter_data, iter_name, iter_number, result_json):
                    yield src, _id, _parent, _type
        return

    def _handle_iteration(self, iter_data, iter_name, iter_number, result_json):
        """Generate source documents for iteration data.
        """
        # There should always be a 'parameters' element with 'benchmark'
        # array element inside it.  There is no reason for this to be an
        # array, but it is: we just pick the 0^th (and only element) as
        # the metadata for all the documents we generate.
        try:
            bm_data = iter_data['parameters']['benchmark']
        except Exception as e:
            self.logger.warning("result-data-indexing: bad result data in JSON"
                    " file, {}: {!r}", result_json, e)
            self.counters['bad_result_data_in_json_file'] += 1
            return
        else:
            if not isinstance(bm_data, (list,)):
                self.logger.warning("result-data-indexing: bad result data in"
                        " JSON file, {}: parameters.benchmark is not a list",
                        result_json)
                self.counters['bad_result_data_in_json_file_bm_not_a_list'] += 1
                return
        bm_md = {}
        conflicts = []
        mod_bm_data = []
        # Merge all the benchmark metadata array entries into one, recording
        # conflicts to handle later.
        #
        # First, find the entry that has the benchmark_name field to use that
        # as a the first one to merge.
        found = False
        for entry in bm_data:
            if not found and 'benchmark_name' in entry:
                bm_md.update(entry)
                found = True
            else:
                mod_bm_data.append(entry)
        # Skip results that don't have a "benchmark_name" field.
        try:
            benchmark = bm_md['benchmark_name']
        except KeyError:
            self.logger.warning("result-data-indexing: bad result data in JSON"
                    " file, {}: missing 'benchmark_name' field", result_json)
            self.counters['bad_result_data_in_json_file_missing_bm_name'] += 1
            return
        # Skip any results that we don't support.
        try:
            bm_driver_data = self._benchmarks[benchmark]
        except KeyError:
            # We don't handle this kind of benchmark currently, so we
            # silently skip it.
            return
        else:
            del bm_md['benchmark_name']
            bm_md['name'] = benchmark
        # Rename the benchmark_version field.
        try:
            bmv = bm_md['benchmark_version']
        except KeyError:
            # Ignore a missing benchmark_version field
            pass
        else:
            del bm_md['benchmark_version']
            if bmv is not None:
                bm_md['version'] = bmv
            else:
                # For some result data files the benchmark_version is a "null"
                # value (JSON representation), so no need to replace it as
                # "version".
                pass
        # Next, continue processing the remaining benchmark parameter entries,
        # merging all the keys while looking for conflicts.
        for entry in mod_bm_data:
            for key in entry.keys():
                if key in bm_md:
                    conflicts.append((key, entry[key]))
                else:
                    bm_md[key] = entry[key]
        # Sneak conflicts in as a field with the benchmark name as a
        # prefix, using one or more "_" on conflict.
        key_sep = ""
        while conflicts:
            key_sep += "_"
            new_conflicts = []
            for key, val in conflicts:
                new_key = "{}{}{}".format(benchmark, key_sep, key)
                if new_key in bm_md:
                    new_conflicts.append((key, val))
                else:
                    bm_md[new_key] = val
            conflicts = new_conflicts

        try:
            bm_md['uid_tmpl'] = bm_md['uid']
        except KeyError:
            # Ignore a missing uid field
            pass
        else:
            bm_md['uid'] = ResultData.expand_template(bm_md['uid_tmpl'], bm_md, run=self.run_metadata)

        iteration = _dict_const([
                ( 'run', self.run_metadata ),
                ( 'iteration', _dict_const([
                        ( "name", iter_name ),
                        ( "number", iter_number)
                    ])
                ),
                # The iteration documents have all the benchmark metadata.
                ( 'benchmark', bm_md )
            ])

        # Generate a sequence of JSON documents yielding each one.  The JSON
        # documents are one of two types: a sample document summarizing the
        # metric data for that sample, with its owner iteration summary data;
        # a result-data document containing the individual metric from the
        # array of result data for the given sample.  And iteration can have
        # N samples, so we yield N sample documents, each followed by M result
        # data documents.
        for source, _parent, _type in ResultData.gen_sources(
                iter_data, bm_driver_data, iteration,
                self.mk_abs_timestamp_millis):
            yield source, _make_source_id(source, _parent=_parent), _parent, \
                    _type

    @staticmethod
    def expand_template(templ, d, run=None):
        # match %...% patterns non-greedily.
        s = templ
        for m in re.findall(uid_keyword_pat, s):
            # m[1:-1] strips the initial and final % signs from the match.
            key = m[1:-1]
            try:
                val = d[key]
            except KeyError:
                if key == "benchmark_name":
                    # Fix "benchmark_name" to try to find "name" in the
                    # metadata if available (should be as we rename
                    # benchmark_name to name).
                    try:
                        val = d['name']
                    except KeyError:
                        pass
                    else:
                        s = re.sub(m, val, s)
                if run is not None and key == "controller_host":
                    # Fix "controller_host" to try to find "controller" in the
                    # run metadata if available.
                    try:
                        val = run['controller']
                    except KeyError:
                        pass
                    else:
                        s = re.sub(m, val, s)
                # Keyword not found, ignore
                pass
            else:
                s = re.sub(m, val, s)
        return s

    @staticmethod
    def make_sample_wrapper(mtype, units, datum):
        # Save the samples for the caller, then delete it from the datum.
        samples = datum['samples']
        del datum['samples']
        try:
            datum['closest_sample'] = datum['closest sample']
        except KeyError:
            pass
        else:
            del datum['closest sample']
        try:
            datum['read_or_write'] = datum['read(0) or write(1)']
        except KeyError:
            pass
        else:
            del datum['read(0) or write(1)']
        # Add argument values ...
        datum['measurement_type'] = mtype
        datum['measurement_units'] = units
        # Construct the uid from the template and the values in datum
        # and replace the template with the result.
        datum['uid_tmpl'] = datum['uid']
        datum['uid'] = ResultData.expand_template(datum['uid_tmpl'], datum)
        return datum, samples

    @staticmethod
    def gen_sources(results, sublists, iteration, cvt_ts):
        """Generate actual source documents from the given results object.

        This generator yields: source, parent_id, doc_type
        """
        iteration_md_subset = _dict_const(
                name=iteration['iteration']['name'],
                number=iteration['iteration']['number'])
        run_md_subset = _dict_const([
            ( 'id', iteration['run']['id'] ),
            ( 'name', iteration['run']['name'] )
            ])
        for result_type in ['latency', 'throughput']:
            try:
                result_type_results = results[result_type]
            except KeyError:
                # No results to report.
                pass
            else:
                for sublist in sublists[result_type]:
                    try:
                        result_type_list = result_type_results[sublist]
                    except KeyError:
                        # This sublist does not exist, ignore.
                        continue
                    for result_type_el in result_type_list:
                        sample_md, samples = ResultData.make_sample_wrapper(
                                result_type, sublist, result_type_el)
                        sample_idx = 0
                        for sample in samples:
                            # Reach into the timeseries data to get the first
                            # entry as the start time of the sample, and the
                            # last entry as the ending timestamp of the
                            # sample.
                            try:
                                tseries = sample['timeseries']
                            except KeyError:
                                self.counters['sample_missing_timeseries'] += 1
                                continue
                            start = tseries[0]
                            end = tseries[-1]
                            try:
                                start_ts = cvt_ts(start['date'])
                                end_ts = cvt_ts(end['date'])
                            except KeyError:
                                self.counters['timeseries_missing_date'] += 1
                                continue
                            except BadDate:
                                # Ignore entire sample if start/end timestamps
                                # are bad.  Already counted.
                                continue
                            del sample['timeseries']
                            # Remember the order in which samples were
                            # processed (zero based).
                            sample_md['@idx'] = sample_idx
                            sample_idx += 1
                            # Construct the same name (one based)
                            sample_md['name'] = "sample{:d}".format(sample_idx)
                            sample_md_subset = _dict_const([
                                    ( 'name', sample_md['name'] ),
                                    ( '@idx', sample_md['@idx'] ),
                                    ( 'uid', sample_md['uid'] ),
                                    ( 'measurement_type', sample_md['measurement_type'] ),
                                    ( 'measurement_units', sample_md['measurement_units'] )
                                ])
                            sample_md['start'] = start_ts
                            sample_md['end'] = end_ts
                            # Now we can emit the sample document knowing the
                            # ID of its iteration parent document.
                            source = _dict_const([
                                ( '@timestamp', start_ts ),
                                ( '@timestamp_original', start['date'] ),
                                # Sample documents inherit the run and
                                # iteration data of its parent.
                                ( 'run', iteration['run'] ),
                                ( 'iteration', iteration['iteration'] ),
                                ( 'benchmark', iteration['benchmark'] ),
                                ( 'sample', sample_md )
                            ])
                            sample_id = _make_source_id(source)
                            yield source, None, 'sample'
                            # Now we can yield each entry of the timeseries
                            # data for this sample.
                            prev_ts = None
                            value_idx = 0
                            for res in tseries:
                                orig_ts = res['date']
                                del res['date']
                                if prev_ts is not None:
                                    assert prev_ts <= orig_ts, "prev_ts %r > orig_ts %r" % (prev_ts, orig_ts)
                                ts = cvt_ts(orig_ts)
                                prev_ts = orig_ts
                                # Now we can emit the actual timeseries value
                                # as a small record not having any sample or
                                # iteration data, found only by its parent
                                # sample ID or by its parent identifying
                                # metadata.
                                res['@idx'] = value_idx
                                value_idx += 1
                                try:
                                    res['read_or_write'] = res['read(0) or write(1)']
                                except KeyError:
                                    pass
                                else:
                                    del res['read(0) or write(1)']
                                source = _dict_const([
                                    ( '@timestamp', ts ),
                                    ( '@timestamp_original', orig_ts ),
                                    ( 'run', run_md_subset),
                                    ( 'iteration', iteration_md_subset ),
                                    ( 'sample', sample_md_subset ),
                                    ( 'result', res )
                                    ])
                                yield source, sample_id, 'res'
        return


def mk_result_data_actions(ptb, idxctx):
    rd = ResultData(ptb, idxctx)
    if not rd:
        return
    # sources is a generator
    sources = rd.make_source()
    if not sources:
        return
    for source, source_id, parent_id, doc_type in sources:
        try:
            idx_name = rd.generate_index_name('result-data', source)
        except BadDate:
            # We don't raise this exception because we are already well into
            # indexing so much data that there is no point in stopping
            # now.  The source of the exception has already counted the
            # exception in its operational context.
            pass
        else:
            assert doc_type in ( 'sample', 'res'), \
                    "Invalid result data document type, {}".format(doc_type)
            if doc_type == "res":
                _type = "pbench-result-data"
            else:
                _type = "pbench-result-data-{}".format(doc_type)
            action = _dict_const(
                _op_type=_op_type,
                _index=idx_name,
                _type=_type,
                _id=source_id,
                _source=source
            )
            if parent_id is not None:
                action['_parent'] = parent_id
            yield action
    return


###########################################################################
# Tool data routines

# Handlers' data table / dictionary describing how to process a given tool's
# data files to be indexed.  The outer dictionary holds one dictionary for
# each tool. Each tool entry has one '@prospectus' entry, which records
# behavior and handling controls for that tool, and an optional "patterns"
# list, which contains a handler record for each file that match a given
# pattern emitted by the tool (can be per file or a pattern to match multiple
# files).
#
# The "@prospetus" dictionaries have two fields: "handling", and
# "method". There are three supported values for "handling": "csv", "stdout",
# and "json", corresponding to the types of files from which we'll pull tool
# data.
#
# For tools with a "handling" field value of "json", no "patterns" list of
# handler records is provided since JSON files have their own record format
# that is left in tact for the most part.
#
# For the "method" field, we support:
#   "individual":         used with "csv" handling, indicates the rows from
#                         each individual .csv file form one document with
#                         the columns as field names
#   "unify":              used with "csv" handling, indicates the rows from
#                         all .csv files are merged together to form one
#                         document associated with a timestamp with all the
#                         columns as field names
#   "periodic_timestamp": used with "stdout" handling, timestamps appear
#                         periodicaly delineating data associated with each
#                         timestamp
#   "json":               used with "json" handling, data in a file is an
#                         array of JSON documents
#
# The handler record dictionaries in "patterns" list contain a number of
# fields:
#   required:
#   --------
#     "pattern":   a regular expression string pattern to match files tool
#                  data files
#   optional:
#   --------
#     "converter":    the data type used for the value, "int" or "float"
#     "class":        a given tool might have different "classes" of data
#                     recorded, e.g. CPU, disk, memory, process, etc.
#     "metric":       the metric name for the data in a file, e.g. all
#                     data in a .csv file might be for IOPS (read and
#                     write).
#     "colpat":       for some .csv files, each column header encodes the
#                     identifier of the entity the metric data is about, and
#                     optionally has sub-fields; this field contains the
#                     regular expression pattern for the column header
#     "subfields":    there are some columns that record metric data as a
#                     subfield of the metric, e.g. "read" and "write" iops
#     "metadata":     some identifiers are constructed by combining pieces
#                     of metadata to make a unique ID, this field lists the
#                     possible metadata names that can be extracted
#     "metadata_pat": the regular expression pattern which describes where
#                     the metadata is found in the identifier
#     "subformat":    used with "stdout" handling to further describe which
#                     format the stdout values take
#   unused:
#   ------
#     "display": human readable, or really what is currently used by pbench
#                today in generated html charts
#     "units":   keyword string representing the units of the metric
_known_tool_handlers = {
    'iostat': {
        '@prospectus': {
            # For iostat .csv files, we want to merge all columns into one
            # JSON document
            'handling': 'csv',
            'method': 'unify'
        },
        'patterns': [
            {
                'pattern': re.compile(r'^disk_IOPS\.csv$'),
                'class': None,
                'metric': 'iops',
                'display': 'IOPS',
                'units': 'count_per_sec',
                'subfields': [ 'read', 'write' ],
                'colpat': re.compile(r'(?P<id>.+)-(?P<subfield>read|write)'),
                'converter': float
            }, {
                'pattern': re.compile(r'^disk_Queue_Size\.csv$'),
                'class': None,
                'metric': 'qsize',
                'display': 'Queue_Size',
                'units': 'count',
                'subfields': [],
                'colpat': re.compile(r'(?P<id>.+)'),
                'converter': float
            }, {
                'pattern': re.compile(r'^disk_Request_Merges_per_sec\.csv$'),
                'class': None,
                'metric': 'reqmerges',
                'display': 'Request_Merges',
                'units': 'count_per_sec',
                'subfields': [ 'read', 'write' ],
                'colpat': re.compile(r'(?P<id>.+)-(?P<subfield>read|write)'),
                'converter': float
            }, {
                'pattern': re.compile(r'^disk_Request_Size_in_512_byte_sectors\.csv$'),
                'class': None,
                'metric': 'reqsize',
                'display': 'Request_Size',
                'units': 'count_512b_sectors',
                'subfields': [],
                'colpat': re.compile(r'(?P<id>.+)'),
                'converter': float
            }, {
                'pattern': re.compile(r'^disk_Throughput_MB_per_sec\.csv$'),
                'class': None,
                'metric': 'tput',
                'display': 'Throughput',
                'units': 'MB_per_sec',
                'subfields': [ 'read', 'write' ],
                'colpat': re.compile(r'(?P<id>.+)-(?P<subfield>read|write)'),
                'converter': float
            }, {
                'pattern': re.compile(r'^disk_Utilization_percent\.csv$'),
                'class': None,
                'metric': 'util',
                'display': 'Utilization',
                'units': 'percent',
                'subfields': [],
                'colpat': re.compile(r'(?P<id>.+)'),
                'converter': float
            }, {
                'pattern': re.compile(r'^disk_Wait_Time_msec\.csv$'),
                'class': None,
                'metric': 'wtime',
                'display': 'Wait_Time',
                'units': 'msec',
                'subfields': [ 'read', 'write' ],
                'colpat': re.compile(r'(?P<id>.+)-(?P<subfield>read|write)'),
                'converter': float
            }
        ]
    },
    'pidstat': {
        '@prospectus': {
            # For pidstat .csv files, we want to individually index
            # each column entry as its own JSON document
            'handling': 'csv',
            'method': 'unify'
        },
        'patterns': [
            {
                'pattern': re.compile(r'^context_switches_nonvoluntary_switches_sec\.csv$'),
                'class': 'context_switches',
                'metric': 'nonvoluntary',
                'display': 'Context_Switches_Nonvoluntary',
                'units': 'count_per_sec',
                'subfields': [],
                'colpat': re.compile(r'(?P<id>.+)'),
                'metadata': [ 'pid', 'command' ],
                'metadata_pat': re.compile(r'(?P<pid>.+?)-(?P<command>.+)'),
                'converter': float
            }, {
                'pattern': re.compile(r'^context_switches_voluntary_switches_sec\.csv$'),
                'class': 'context_switches',
                'metric': 'voluntary',
                'display': 'Context_Switches_Voluntary',
                'units': 'count_per_sec',
                'subfields': [],
                'colpat': re.compile(r'(?P<id>.+)'),
                'metadata': [ 'pid', 'command' ],
                'metadata_pat': re.compile(r'(?P<pid>.+?)-(?P<command>.+)'),
                'converter': float
            }, {
                'pattern': re.compile(r'^cpu_usage_percent_cpu\.csv$'),
                'class': 'cpu',
                'metric': 'usage',
                'display': 'CPU_Usage',
                'units': 'percent_cpu',
                'subfields': [],
                'colpat': re.compile(r'(?P<id>.+)'),
                'metadata': [ 'pid', 'command' ],
                'metadata_pat': re.compile(r'(?P<pid>.+?)-(?P<command>.+)'),
                'converter': float
            }, {
                'pattern': re.compile(r'^file_io_io_reads_KB_sec\.csv$'),
                'class': 'io',
                'metric': 'reads',
                'display': 'IO_Reads',
                'units': 'KB_per_sec',
                'subfields': [],
                'colpat': re.compile(r'(?P<id>.+)'),
                'metadata': [ 'pid', 'command' ],
                'metadata_pat': re.compile(r'(?P<pid>.+?)-(?P<command>.+)'),
                'converter': float
            }, {
                'pattern': re.compile(r'^file_io_io_writes_KB_sec\.csv$'),
                'class': 'io',
                'metric': 'writes',
                'display': 'IO_Writes',
                'units': 'KB_per_sec',
                'subfields': [],
                'colpat': re.compile(r'(?P<id>.+)'),
                'metadata': [ 'pid', 'command' ],
                'metadata_pat': re.compile(r'(?P<pid>.+?)-(?P<command>.+)'),
                'converter': float
            }, {
                'pattern': re.compile(r'^memory_faults_major_faults_sec\.csv$'),
                'class': 'memory',
                'metric': 'faults_major',
                'display': 'Memory_Faults_Major',
                'units': 'count_per_sec',
                'subfields': [],
                'colpat': re.compile(r'(?P<id>.+)'),
                'metadata': [ 'pid', 'command' ],
                'metadata_pat': re.compile(r'(?P<pid>.+?)-(?P<command>.+)'),
                'converter': float
            }, {
                'pattern': re.compile(r'^memory_faults_minor_faults_sec\.csv$'),
                'class': 'memory',
                'metric': 'faults_minor',
                'display': 'Memory_Faults_Minor',
                'units': 'count_per_sec',
                'subfields': [],
                'colpat': re.compile(r'(?P<id>.+)'),
                'metadata': [ 'pid', 'command' ],
                'metadata_pat': re.compile(r'(?P<pid>.+?)-(?P<command>.+)'),
                'converter': float
            }, {
                'pattern': re.compile(r'^memory_usage_resident_set_size\.csv$'),
                'class': 'memory',
                'metric': 'rss',
                'display': 'RSS',
                'units': 'KB',
                'subfields': [],
                'colpat': re.compile(r'(?P<id>.+)'),
                'metadata': [ 'pid', 'command' ],
                'metadata_pat': re.compile(r'(?P<pid>.+?)-(?P<command>.+)'),
                'converter': int
            }, {
                'pattern': re.compile(r'^memory_usage_virtual_size\.csv$'),
                'class': 'memory',
                'metric': 'vsz',
                'display': 'VSZ',
                'units': 'KB',
                'subfields': [],
                'colpat': re.compile(r'(?P<id>.+)'),
                'metadata': [ 'pid', 'command' ],
                'metadata_pat': re.compile(r'(?P<pid>.+?)-(?P<command>.+)'),
                'converter': int
            }
        ]
    },
    'vmstat': {
        '@prospectus': {
            'handling': 'csv',
            'method': 'unify'
        },
        'patterns': [
            {
                'pattern': re.compile(r'^vmstat_block\.csv$'),
                'class': None,
                'metric': 'block',
                'units': 'KiB',
                'subfields': [ 'in', 'out' ],
                'colpat': re.compile(r'(?P<subfield>in|out)_KiB'),
                'converter': int
            }, {
                'pattern': re.compile(r'^vmstat_cpu\.csv$'),
                'class': None,
                'metric': 'cpu',
                'units': '%usage',
                'subfields': [ 'idle', 'steal', 'sys', 'user', 'wait' ],
                'colpat': re.compile(r'(?P<subfield>idle|steal|sys|user|wait)'),
                'converter': int
            }, {
                'pattern': re.compile(r'^vmstat_memory\.csv$'),
                'class': None,
                'metric': 'memory',
                'units': 'KiB',
                'subfields': [ 'active', 'free', 'inactive', 'swapped' ],
                'colpat': re.compile(r'(?P<subfield>active|free|inactive|swapped)_KiB'),
                'converter': int
            }, {
                'pattern': re.compile(r'^vmstat_procs\.csv$'),
                'class': None,
                'metric': 'procs',
                'units': 'count',
                'subfields': [ 'blocked', 'running' ],
                'colpat': re.compile(r'(?P<subfield>blocked|running)'),
                'converter': int
            }, {
                'pattern': re.compile(r'^vmstat_swap\.csv$'),
                'class': None,
                'metric': 'swap',
                'units': 'KiB',
                'subfields': [ 'in', 'out' ],
                'colpat': re.compile(r'(?P<subfield>in|out)_KiB'),
                'converter': int
            }, {
                'pattern': re.compile(r'^vmstat_system\.csv$'),
                'class': None,
                'metric': 'system',
                'units': 'count',
                'subfields': [ 'cntx_switches', 'interrupts' ],
                'colpat': re.compile(r'(?P<subfield>cntx_switches|interrupts)'),
                'converter': int
            }
        ]
    },
    'mpstat': {
        '@prospectus': {
            # For mpstat .csv files, we want to individually index each row of
            # a file as its own JSON document.
            'handling': 'csv',
            'method': 'individual'
        },
        'patterns': [
            {
                # The mpstat tool produces csv files with names based on cpu
                # cores. The number of cpu cores can be different on each
                # computer, so map a regular expression for each file type.
                'pattern': re.compile(r'^(?P<id>cpu.+)_cpu\w+\.csv$'),
                'class': None,
                'metric': 'cpu',
                'display': 'CPU',
                'units': 'percent_cpu',
                'converter': float
            }
        ]
    },
    'proc-interrupts': {
        '@prospectus': {
            'handling': 'stdout',
            'method': 'periodic_timestamp'
        },
        'patterns': [
            {
                'pattern': re.compile(r'^proc-interrupts-stdout\.txt$'),
                'subformat': 'procint',
                'converter': int
            }
        ]
    },
    'proc-vmstat': {
        # The proc-vmstat tool writes the timestamp and key value pairs to
        # the stdout text file which is not json or csv.
        '@prospectus': {
            'handling': 'stdout',
            'method': 'periodic_timestamp'
        },
        'patterns': [
            {
                'pattern': re.compile(r'^proc-vmstat-stdout\.txt$'),
                'subformat': 'keyval',
                'converter': int
            }
        ]
    },
    'prometheus-metrics': {
        '@prospectus': {
            'handling': 'json',
            'method': 'json'
        }
    },
    # The following tools should be processed via JSON data generated from the
    # sysstat tool suite itself, which we currently don't handle.
    'sar': None,
    # The following tools currently don't have output that is readily
    # indexable:
    'turbostat': None,
    'perf': None
}

# If we need to deal with old .csv file names, place an alias here to map to
# an existing handler above.
_aliases = {
    'disk_Request_Merges.csv': 'disk_Request_Merges_per_sec.csv',
    'disk_Request_Size.csv': 'disk_Request_Size_in_512_byte_sectors.csv',
    'disk_Throughput.csv': 'disk_Throughput_MB_per_sec.csv',
    'disk_Utilization.csv': 'disk_Utilization_percent.csv',
    'disk_Wait_Time.csv': 'disk_Wait_Time_msec.csv',
}

def _noop(arg):
    return arg


class ToolData(PbenchData):
    def __init__(self, ptb, iteration, sample, host, tool, idxctx):
        super().__init__(ptb, idxctx)
        self.toolname = tool
        idxctx.opctx.append(_dict_const(object="ToolData-%s" % (tool), counters=self.counters))
        try:
            iterseqno = int(iteration.split('-', 1)[0])
        except ValueError:
            iterseqno = -1
        itername = iteration

        self.iteration_metadata = _dict_const(
            name=itername,
            number=iterseqno,
        )
        self.sample_metadata = _dict_const(
            name=sample,
            hostname=host
        )

        try:
            self.handler = _known_tool_handlers[tool]
        except KeyError:
            self.handler = None
            self.files = None
            self.basepath = None
        else:
            toolsgroup = ptb.run_metadata['toolsgroup']
            self.run_metadata['toolsgroup'] = toolsgroup
            # Impedance match between host names used when registering tools
            # and <label>:<hostname_s> convention used when collecting the
            # results. Usually when labels are found the on-disk directory
            # name where tool data is stored is <label>:<hostname_s>. But when
            # a full hostname was used to register the tool, that can be used
            # for the on-disk directory name instead of the short
            # hostname. And it seems there were different versions of the
            # agent that behaved in reverse.  So instead of just guessing at
            # which one to use, we try all three combinations.
            files = None
            try:
                label = ptb.mdconf.get("tools/{}".format(host), "label")
            except Exception:
                label = ""
            try:
                hostname_s = ptb.mdconf.get("tools/{}".format(host), "hostname-s")
            except Exception:
                hostname_s = ""
            basepath_tmpl = os.path.join(ptb.dirname, iteration, sample, "tools-{0}".format(toolsgroup), "{}", tool)
            if label and hostname_s:
                hostpath = "{}:{}".format(label, hostname_s)
                # Fetch all the data files as a dictionary containing metadata
                # about them.
                basepath = basepath_tmpl.format(hostpath)
                files = ToolData.get_files(self.handler, basepath, toolsgroup, tool, ptb)
            if not files and hostname_s:
                # Fetch all the data files as a dictionary containing metadata
                # about them.
                basepath = basepath_tmpl.format(hostname_s)
                files = ToolData.get_files(self.handler, basepath, toolsgroup, tool, ptb)
            if not files:
                # Fetch all the data files as a dictionary containing metadata
                # about them.
                basepath = basepath_tmpl.format(host)
                files = ToolData.get_files(self.handler, basepath, toolsgroup, tool, ptb)
            self.basepath = basepath
            self.files = files

    def _make_source_unified(self):
        """Create one JSON document per identifier, per timestamp from
        the data found in multiple csv files.

        This algorithm is only applicable to 2 or more csv files which
        contain data about 1 or more identifiers.

        The approach is to process each .csv file at the same time,
        reading one row from each in lock step. The field data found
        in each column across all files for a given identifier at the
        same timestamp are unified into one JSON document.

        For example, given 2 csv files:

          * file0.csv
            * timestamp_ms,id0_foo,id1_foo,id2_foo
              * 00000, 1.0, 2.0, 3.0
              * 00001, 1.1, 2.1, 3.1
          * file1.csv
            * timestamp_ms,id0_bar,id1_bar,id2_bar
              * 00000, 4.0, 5.0, 6.0
              * 00001, 4.1, 5.1, 6.1

        The output would be 6 JSON records, one for each 3 identifiers
        at each of two timestamps, with the fields "foo" and "bar" in
        each:

          [ { "@timestamp": 00000, "id": "id0", "foo": 1.0, "bar": 4.0 },
            { "@timestamp": 00000, "id": "id1", "foo": 2.0, "bar": 5.0 },
            { "@timestamp": 00000, "id": "id2", "foo": 3.0, "bar": 6.0 },
            { "@timestamp": 00001, "id": "id0", "foo": 1.1, "bar": 4.1 },
            { "@timestamp": 00001, "id": "id1", "foo": 2.1, "bar": 5.1 },
            { "@timestamp": 00001, "id": "id2", "foo": 3.1, "bar": 6.1 } ]
        """
        # Class list is generated from the handler data
        class_list = _dict_const()
        # The metric mapping provides (klass, metric) tuples for a given
        # .csv file.
        metric_mapping = _dict_const()
        # The list of identifiers is generated from the combined headers,
        # parsing out the IDs
        identifiers = _dict_const()
        # Records the association between the column number of a given
        # .csv file and the identifier / subfield tuple.
        field_mapping = _dict_const()
        # Metadata extracted from column header
        metadata = _dict_const()

        # To begin the unification process, we have to generate a data
        # structure to drive processing of the rows from all csv files
        # by deriving data from the header rows of all the csv files,
        # first. This is driven by the data provided in the handler.
        self.logger.info("tool-data-indexing: tool {}, start unified for {}", self.toolname, self.basepath)
        for csv in self.files:
            # Each csv file dictionary provides its header row.
            header = csv['header']
            if header[0] != 'timestamp_ms':
                self.logger.warning("tool-data-indexing: expected first column of"
                        " .csv file ({}) to be 'timestamp_ms', found '{}'",
                        csv['basename'], header[0])
                self.counters['first_column_not_timestamp_ms'] += 1
                continue
            handler_rec = csv['handler_rec']
            if handler_rec['class'] is not None:
                class_list[handler_rec['class']] = True
            try:
                converter = handler_rec['converter']
            except KeyError:
                converter = _noop
            metric_mapping[csv['basename']] = (handler_rec['class'], handler_rec['metric'], converter)
            colpat = handler_rec['colpat']
            if csv['basename'] not in field_mapping:
                field_mapping[csv['basename']] = _dict_const()
            for idx,col in enumerate(header):
                if idx == 0:
                    # No field mapping necessary for the timestamp
                    field_mapping[csv['basename']][idx] = None
                    continue
                # First pull out the identifier of the target from the column
                # header and record it in the list of identifiers.
                m = colpat.match(col)
                try:
                    identifier = m.group('id')
                except IndexError:
                    identifier = "__none__"
                identifiers[identifier] = True
                try:
                    # Pull out any sub-field names found in the column
                    # header.
                    subfield = m.group('subfield')
                except IndexError:
                    # Columns do not have to have sub-fields, so we can
                    # safely use None.
                    subfield = None
                else:
                    # Ensure the name of the subfield found in the
                    # column is in the list of expected subfields from
                    # "known handlers" table.
                    if subfield not in handler_rec['subfields']:
                        self.logger.warning("tool-data-indexing: column header,"
                                " {:r}, has an unexpected subfield, {:r},"
                                " expected {:r} subfields, for .csv {}",
                                col, subfield, handler_rec['subfields'],
                                csv['basename'])
                        self.counters['column_subfields_do_not_match_handler'] += 1
                        subfield = None
                # Record the association between the column number
                # ('idx') of a given .csv file ('basename') and the
                # identifier / subfield tuple.
                field_mapping[csv['basename']][idx] = (identifier, subfield)
                try:
                    # Some identifiers are constructed by combining
                    # pieces of metadata to make a unique ID.  Pull
                    # out of the handler the pattern that can extract
                    # that metadata.
                    metadata_pat = handler_rec['metadata_pat']
                except KeyError:
                    # We can safely ignore handlers which do not
                    # provide metadata handlers.
                    pass
                else:
                    # Parse out the metadata name(s) from the column
                    # header.
                    m = metadata_pat.match(col)
                    if m:
                        colmd = _dict_const()
                        # We matched one or more names, loop through
                        # the list of expected metadata regex group
                        # names to build up the mapping of regex
                        # group names to actual metadata field names.
                        for md in handler_rec['metadata']:
                            try:
                                val = m.group(md)
                            except IndexError:
                                self.logger.warning("tool-data-indexing: handler"
                                        " metadata, {:r}, not found in column"
                                        " {:r} using pattern {:r}, for .csv"
                                        " '{}'", handler_rec['metadata'], col,
                                        handler_rec['metadata_pat'],
                                        csv['basename'])
                                self.counters['expected_column_metadata_not_found'] += 1
                            else:
                                colmd[md] = val
                        # Store the association between the identifier
                        # and the metadata mapping for field names.
                        if colmd:
                            metadata[identifier] = colmd
        # At this point, we have processed all the data about csv files
        # and are ready to start reading the contents of all the csv
        # files and building the unified records.
        def rows_generator():
            # We use this generator to highlight the process of reading from
            # all the csv files, reading one row from each of the csv files,
            # returning that as a dictionary of csv file to row read, which
            # in turn is yielded by the generator.
            idx = 0
            while True:
                # Read a row from each .csv file
                rows = _dict_const()
                for csv in self.files:
                    try:
                        rows[csv['basename']] = next(csv['reader'])
                    except StopIteration:
                        # This should handle the case of mismatched number of
                        # rows across all .csv files. All readers which have
                        # finished will emit a StopIteration.
                        pass
                if not rows:
                    # None of the csv file readers returned any rows to
                    # process, so we're done.
                    break
                # Yield the one dictionary that contains each newly read row
                # from all the csv files.
                yield idx, rows
                idx += 1
        self.logger.info("tool-data-indexing: tool {}, gen unified begin for {}", self.toolname, self.basepath)
        prev_ts = None
        for idx, rows in rows_generator():
            # Verify timestamps are all the same for this row.
            tstamp = None
            first = None
            for fname in rows.keys():
                tstamp = rows[fname][0]
                if first is None:
                    first = tstamp
                elif first != tstamp:
                    self.logger.warning("tool-data-indexing: {} csv files have"
                            " inconsistent timestamps per row", self.toolname)
                    self.counters['inconsistent_timestamps_across_csv_files'] += 1
                    break
            # We are now ready to create a base document per identifier to
            # hold all the fields from the various columns. Given the two
            # input dictionaries, "identifiers" and "metadata", we create
            # an output dictionary, "datum", which has keys for all the
            # identifiers and a base dictionary for forming the JSON docs.

            # For example, given these inputs:
            #   * identifiers = { "id0": True, "id1": True }
            #   * metadata = { "id0": { "f1": "foo", "f2": "bar" },
            #                  "id1": { "f1": "faz", "f2": "baz" } }
            # The for loop below would generate the following dictionary:
            #   * datum = { "id0": { "@timestamp": ts_str,
            #                        "run": self.run_metadata,
            #                        "sample": self.sample_metadata,
            #                        "iteration": self.iteration_metadata,
            #                        self.toolname: { "id": "id0",
            #                                         "f1": "foo",
            #                                         "f2": "bar" } },
            #               "id1": { "@timestamp": ts_str,
            #                        "run": self.run_metadata,
            #                        "sample": self.sample_metadata,
            #                        "iteration": self.iteration_metadata,
            #                        self.toolname: { "id": "id1",
            #                                         "f1": "faz",
            #                                         "f2": "baz" } },

            # The timestamp is taken from the "first" timestamp, converted
            # to a floating point value in seconds, and then formatted as a
            # string.
            if prev_ts is not None:
                assert prev_ts <= first, "prev_ts %r > first %r" % (prev_ts, first)
            ts_val = self.mk_abs_timestamp_millis(first)
            prev_ts = first
            datum = _dict_const()
            for identifier in identifiers.keys():
                datum[identifier] = _dict_const([
                    # Since they are all the same, we use the first to
                    # generate the real timestamp.
                    ('@timestamp', ts_val),
                    ('@timestamp_original', str(first)),
                    ('run', self.run_metadata),
                    ('iteration', self.iteration_metadata),
                    ('sample', self.sample_metadata),
                    (self.toolname, _dict_const())
                ])
                if identifier != "__none__":
                    datum[identifier][self.toolname]['id'] = identifier
                datum[identifier][self.toolname]['@idx'] = idx
                try:
                    md = metadata[identifier]
                except KeyError:
                    pass
                else:
                    datum[identifier][self.toolname].update(md)
                for klass in class_list.keys():
                    datum[identifier][self.toolname][klass] = _dict_const()
            # Now we can perform the mapping from multiple .csv files to JSON
            # documents using a known field hierarchy (no identifiers in field
            # names) with the identifiers as additional metadata. Note that we
            # are constructing this document just from the current row of data
            # taken from all .csv files (assumes timestamps are the same).
            for fname,row in rows.items():
                klass, metric, converter = metric_mapping[fname]
                for idx,val in enumerate(row):
                    if idx == 0:
                        continue
                    # Given an fname and a column offset, return the
                    # identifier from the header
                    identifier, subfield = field_mapping[fname][idx]
                    if klass is not None:
                        _d = datum[identifier][self.toolname][klass]
                    else:
                        _d = datum[identifier][self.toolname]
                    if subfield:
                        if metric not in _d:
                            _d[metric] = _dict_const()
                        _d[metric][subfield] = converter(val)
                    else:
                        _d[metric] = converter(val)
            # At this point we have fully mapped all data from all .csv files
            # to their proper fields for each identifier. Now we can yield
            # records for each of the identifiers.
            for _id,source in datum.items():
                source_id = _make_source_id(source)
                yield source, source_id
        self.logger.info("tool-data-indexing: tool {}, end unified for {}", self.toolname, self.basepath)
        return

    def _make_source_individual(self):
        """Read .csv files individually, emitting records for each row and
        column coordinate."""
        for csv in self.files:
            assert csv['header'][0] == 'timestamp_ms', \
                    "Unexpected time stamp header, '{}'".format(
                        csv['header'][0])
            header = csv['header']
            handler_rec = csv['handler_rec']
            klass = handler_rec['class']
            metric = handler_rec['metric']
            try:
                converter = handler_rec['converter']
            except KeyError:
                converter = _noop
            reader = csv['reader']
            ts = None

            if 'pattern' not in handler_rec:
                # No pattern to consider to find matching files.
                continue
            match = handler_rec['pattern'].match(csv['basename'])
            if not match:
                # The pattern does not match the basename, skip this file.
                continue
            # We only handle files that have the id in the filename pattern.
            try:
                datum_id = match.group('id')
            except IndexError:
                # This handler does not have an id, skip this file.
                break
            prev_ts = None
            idx = 0
            self.logger.info("tool-data-indexing: tool {}, individual start {}", self.toolname, csv['path'])
            for row in reader:
                for col,val in enumerate(row):
                    # The timestamp column is index zero.
                    if col == 0:
                        if prev_ts is not None:
                            assert prev_ts <= val, "prev_ts %r > val %r" % (prev_ts, val)
                        ts_val = self.mk_abs_timestamp_millis(val)
                        prev_ts = val
                        datum = _dict_const()
                        datum['@timestamp'] = ts_val
                        datum['@timestamp_original'] = val
                        datum['run'] = self.run_metadata
                        datum['iteration'] = self.iteration_metadata
                        datum['sample'] = self.sample_metadata
                        datum[self.toolname] = _dict_const([('id', datum_id)])
                        datum[self.toolname]['@idx'] = idx
                        if klass is not None:
                            _d = datum[self.toolname][klass] = _dict_const()
                        else:
                            _d = datum[self.toolname]
                        _d[metric] = _dict_const()
                    else:
                        column = header[col]
                        _d[metric][column] = float(val)

                source_id = _make_source_id(datum)
                yield datum, source_id
                idx += 1
            self.logger.info("tool-data-indexing: tool {}, individual end {}", self.toolname, csv['path'])
        return

    # For some tools, proc-vmstat being the first case we encounter this,
    # depending on the version of the tool run and the version of the OS on
    # which the tool is run, the key names emitted can change version to
    # version.  When they do, sometimes this can cause a mapping conflict with
    # the data types from the two (or more) versions.  To avoid such
    # conflicts, we pick a key that does not have a substat to rename to
    # resolve the conflict.
    #
    # For example, one version of proc-vmstat will emit a key such as:
    #     pgrefill: 1000
    # Then another version will emit a key such as:
    #     pgrefill_bar: 10
    #     pgrefill_foo: 20
    # When that happens, we'll have two different JSON documents for each, one
    # has stat "pgrefill" with a value, the other has stat "pgrefill" as an
    # object with substats "foo" and "bar":
    #     { "pgrefill": 1000 }
    #     { "pgrefill": { "foo": 20, "bar": 10 } }
    # Both of those documents can't land in the same index because the
    # mappings for "pgrefill" are radically different.
    #
    # So this table gives us a place to rename the key without a substat to
    # avoid the conflict.
    _remaps = {
        "proc-vmstat": {
            "key": {
                "allocstall": "allocstall_",
                "pgrefill": "pgrefill_"
            },
            "stat": None,
            "substat": None
        }
    }

    def _stdout_keyval(self, file_object, converter, path):
        """Process a line of a stdout key/value pair output file, building up the
        record (dict) by adding each key/value pair found, associating them
        with the previously encountered timestamp.  A record is yielded as one
        JSON object when indexed.

        The format for files considered by this method is as follows:

         * each line of the file contains an ascii-numeric key and a
           numeric (integer or floating point) value separated by a ':'
         * the keyword, `timestamp`, is recognized to be the
           timestamp value to be associated with all following
           key/value pairs until the next `timestamp` keyword
           is encountered
         * all key/value pairs are treated as fields of one JSON
           document with the associated timestamp to be indexed

        An example file format:

        timestamp: 12345.00
        key0: 100.0
        key1: 100.1
        ...
        keyN: 100.N
        timestamp: 12345.01
        key0: 100.0
        key1: 100.1
        ...
        keyN: 100.N
        timestamp: ...

        """
        record = None
        prev_gauge = None
        ts_orig = None
        prev_ts_orig = None
        try:
            # Fetch the remaps table to see if any naming conflicts need to be
            # resolved.
            remaps = self._remaps[self.toolname]
        except KeyError:
            remaps = None
        idx = 0
        self.logger.info("tool-data-indexing: tool {}, stdout keyval start {}", self.toolname, path)
        for line in file_object:
            if line.startswith('timestamp:'):
                prev_ts_orig = ts_orig
                if record:
                    # timestamp delimits records, yield last record.
                    if not record[self.toolname]['rate']:
                        # For first record, rate will be empty, so
                        # don't emit it.
                        del record[self.toolname]['rate']
                    yield record
                    idx += 1
                    # Be sure to remember the record we just emitted
                    # so that it is available for rate calculations.
                    prev_gauge = record[self.toolname]['gauge']
                # Get the second column, the timestamp value, which is
                # *seconds* since the epoch, and then convert to millis
                # since the epoch.
                ts_orig = float(line.split(':')[1])
                if prev_ts_orig is not None:
                    assert prev_ts_orig <= ts_orig, "prev_ts_orig %r > ts_orig %r" % (prev_ts_orig, ts_orig)
                ts_str = self.mk_abs_timestamp_millis(ts_orig * 1000)
                record = _dict_const()
                record['@timestamp'] = ts_str
                record['@timestamp_original'] = str(ts_orig)
                record['run'] = self.run_metadata
                record['iteration'] = self.iteration_metadata
                record['sample'] = self.sample_metadata
                record[self.toolname] = _dict_const()
                record[self.toolname]['@idx'] = idx
                record[self.toolname]['gauge'] = gauge = _dict_const()
                record[self.toolname]['rate'] = rate = _dict_const()
            elif ts_orig is None:
                # We have not encountered a timestamp yet, so ignore
                # all lines until the first timestamp.
                continue
            else:
                key, value = line.strip().split(' ')
                parts = key.split('_', 1)
                if len(parts) == 1:
                    # For keys that are not split into stat and substat, look
                    # to see if the stat needs to be rename to avoid conflict
                    # with other keys that might share the same prefix.
                    if remaps is not None:
                        try:
                            stat = remaps['key'][key]
                        except KeyError:
                            stat = key
                    else:
                        stat = key
                    gauge[stat] = converter(value)
                    if prev_ts_orig:
                        # Note we don't record the rate on the first value
                        # encountered.
                        duration = ts_orig - prev_ts_orig
                        value_diff = int(value) - prev_gauge[stat]
                        the_rate = value_diff / duration
                        rate[stat] = the_rate
                else:
                    assert len(parts) == 2, "Logic bomb! parts is not parts!"
                    stat = parts[0]
                    substat = parts[1]
                    if stat not in gauge:
                        gauge[stat] = _dict_const()
                    gauge[stat][substat] = converter(value)
                    if prev_ts_orig:
                        # Note we don't record the rate on the first value
                        # encountered.
                        duration = (ts_orig/1000) - (prev_ts_orig/1000)
                        value_diff = int(value) - prev_gauge[stat][substat]
                        the_rate = value_diff / duration
                        if stat not in rate:
                            rate[stat] = _dict_const()
                        rate[stat][substat] = the_rate
        if record and record[self.toolname]['gauge']:
            yield record
        self.logger.info("tool-data-indexing: tool {}, stdout keyval end {}", self.toolname, path)

    def _stdout_procint(self, file_object, converter, path):
        """Process the two-dimensional proc-interrupts output.

        An example file format:
        timestamp: 1394048617.043209234
                   CPU0       CPU1       CPU2       CPU3
          0:         25          0          0          0   IO-APIC-edge      timer
          1:         10          0          0          0   IO-APIC-edge      i8042
        NMI:          0          0          0          0   Non-maskable interrupts
        LOC:      48687      45068      40188      65602   Local timer interrupts
        SPU:          0          0          0          0   Spurious interrupts
        """
        cpu_column_ids = None
        cpu_count = None
        ts_str = None
        ts_orig = None
        prev_ts_orig = None
        prev_gauges = _dict_const()
        idx = 0
        self.logger.info("tool-data-indexing: tool {}, stdout procint start {}", self.toolname, path)
        for line in file_object:
            if line.startswith('timestamp:'):
                idx += 1
                prev_ts_orig = ts_orig
                # Get the second column, the timestamp value, which is
                # *seconds* since the epoch, and then convert to millis
                # since the epoch.
                ts_orig = float(line.split(':')[1])
                if prev_ts_orig is not None:
                    assert prev_ts_orig <= ts_orig, "prev_ts_orig %r > ts_orig %r" % (prev_ts_orig, ts_orig)
                ts_str = self.mk_abs_timestamp_millis(ts_orig * 1000)
                # The next line is assumed to be the header, so instead of
                # looping to get to it, we just pull it out and process it
                # here.
                header = next(file_object)
                columns = header.split()
                cpu_column_ids = []
                for cpu in columns:
                    if not cpu.startswith("CPU"):
                        raise Exception("Bad proc-interrupts-stdout.txt file encountered")
                    cpu_column_ids.append(cpu[3:])
                cpu_count = len(cpu_column_ids)
                continue
            parts = line[:-1].split(None, 1 + cpu_count)
            int_id = parts[0][:-1]
            if int_id in ( 'ERR', 'MIS' ):
                record = _dict_const()
                record['@timestamp'] = ts_str
                record['@timestamp_original'] = str(ts_orig)
                record['run'] = self.run_metadata
                record['iteration'] = self.iteration_metadata
                record['sample'] = self.sample_metadata
                record[self.toolname] = _dict_const()
                record[self.toolname]['@idx'] = idx
                record[self.toolname]['int_id'] = int_id
                record[self.toolname]['gauge'] = value = converter(parts[1])
                if int_id in prev_gauges:
                    duration = ts_orig - prev_ts_orig
                    value_diff = value - prev_gauges[int_id]
                    the_rate = value_diff / duration
                    record[self.toolname]['rate'] = the_rate
                prev_gauges[int_id] = value
                yield record
            else:
                desc_str = parts[-1]
                col = 1
                records = []
                cpu_gauges = []
                for cpu in cpu_column_ids:
                    val = converter(parts[col])
                    col += 1
                    record = _dict_const()
                    record['@timestamp'] = ts_str
                    record['@timestamp_original'] = str(ts_orig)
                    record['run'] = self.run_metadata
                    record['iteration'] = self.iteration_metadata
                    record['sample'] = self.sample_metadata
                    record[self.toolname] = _dict_const()
                    record[self.toolname]['@idx'] = idx
                    record[self.toolname]['int_id'] = int_id
                    record[self.toolname]['cpu_id'] = cpu
                    record[self.toolname]['desc'] = desc_str
                    record[self.toolname]['gauge'] = val
                    records.append(record)
                    cpu_gauges.append(val)
                if int_id in prev_gauges:
                    prev_cpu_gauges = prev_gauges[int_id]
                    col = 0
                    duration = ts_orig - prev_ts_orig
                    for record in records:
                        value_diff = record[self.toolname]['gauge'] - prev_cpu_gauges[col]
                        the_rate = value_diff / duration
                        record[self.toolname]['rate'] = the_rate
                prev_gauges[int_id] = cpu_gauges
                for record in records:
                    yield record
        self.logger.info("tool-data-indexing: tool {}, stdout procint end {}", self.toolname, path)
        return

    _subformats = {
        'procint': _stdout_procint,
        'keyval': _stdout_keyval,
        }

    def _make_source_stdout(self):
        """Read the given set of files one at a time, emitting a record for each data
        set associated with a timestamp. The timestamp is expected to be on a
        line by itself, formatted as:

            timestamp: 12345.00

        Where the timestamp value represents the number of seconds since the epoch.

        Following that timestamp line will be a payload of data formatted in
        one of the supported "sub-formats" (see _subformats array above).
        """
        for output_file in self.files:
            basename = output_file['basename']
            handler_rec = output_file['handler_rec']
            subformat = handler_rec['subformat']
            try:
                converter = handler_rec['converter']
            except KeyError:
                converter = _noop
            try:
                func = self._subformats[subformat]
            except KeyError:
                self.logger.warning("tool-data-indexing: encountered unrecognized"
                        " sub-format, '{}', not one of {!r}", subformat,
                        [key for key in self._subformats.keys()])
                self.counters["unrecognized_subformat"] += 1
                continue
            path = os.path.join(self.ptb.extracted_root, output_file['path'])
            with open(path, 'r') as file_object:
                for record in func(self, file_object, converter, output_file['path']):
                    source_id = _make_source_id(record)
                    yield record, source_id

    def _make_source_json(self):
        """Process JSON files in the form of an outer JSON array of ready to
           source documents.  It is expected that each source document has an
           "@timestamp" field as either an ISO format string,
           "YYYY-mm-ddTHH:MM:SS.ssssss", or as a unix seconds since the epoch
           floating point timestamp value.

           Any JSON document missing an "@timestamp" field is ignored.  Each
           JSON document will have its "@timestamp" field validated that it
           lands within the start/end run time frame.  The source JSON that
           will be indexed into Elasticsearch will convert the "@timetamp"
           value to millis since the epoch.
        """
        for df in self.files:
            try:
                with open(os.path.join(self.ptb.extracted_root, df['path'])) as fp:
                    payload = json.load(fp)
            except Exception as e:
                self.logger.warning("tool-data-indexing: encountered bad JSON"
                        " file, {}: {:r}", df['path'], e)
                self.counters["bad_json_file"] += 1
                continue

            missing_ts = False
            invalid_ts = False
            badrange_ts = False
            idx = 0
            self.logger.info("tool-data-indexing: tool {}, json start {}", self.toolname, df['path'])
            for payload_source in payload:
                try:
                    ts_val = payload_source['@timestamp']
                except KeyError:
                    # Missing timestamps
                    if not missing_ts:
                        # Log the first record with missing timestamps we
                        # encounter for this file, and then count the rest and
                        # report the count with the summary of how the
                        # indexing went.
                        missing_ts = True
                        self.logger.warning("tool-data-indexing: encountered JSON"
                                " file, {}, with missing @timestamp fields",
                                df['path'])
                    self.counters['json_doc_missing_timestamp'] += 1
                    idx += 1
                    continue
                else:
                    del payload_source['@timestamp']

                # Further timestamp handling
                try:
                    # Unix seconds since epoch timestamp as an absolute time
                    # value.
                    ts = datetime.utcfromtimestamp(ts_val)
                except TypeError:
                    # The timestamp value is not in seconds since the epoch,
                    # so assume that payload_source[@timestamp] is already in
                    # the expected format; validate it.
                    try:
                        ts = datetime.strptime(ts_val, "%Y-%m-%dT%H:%M:%S.%f")
                    except ValueError:
                        if not invalid_ts:
                            invalid_ts = True
                            self.logger.warning("tool-data-indexing: encountered"
                                    " JSON file, {}, with invalid @timestamp"
                                    " fields ('{:r}')", df['path'], ts_val)
                        self.counters['json_doc_timestamp_not_valid'] += 1
                        idx += 1
                        continue
                if ts < self.ptb.start_run_ts or ts > self.ptb.end_run_ts:
                    if not badrange_ts:
                        badrange_ts = True
                        self.logger.warning("tool-data-indexing: encountered JSON"
                                " file, {}, with @timestamp fields out side"
                                " start/end run time range ({:r})",
                                df['path'], ts_val)
                    self.counters['json_doc_timestamp_out_of_range'] += 1
                    idx += 1
                    continue

                source = _dict_const()
                # Convert the validated timestamp into ISO format.
                source['@timestamp'] = ts.strftime("%Y-%m-%dT%H:%M:%S.%f")
                source['@timestamp_original'] = str(ts_val)
                # Add the run metadata
                source['run'] = self.run_metadata
                source['iteration'] = self.iteration_metadata
                source['sample'] = self.sample_metadata
                source[self.toolname] = payload_source
                source[self.toolname]['@idx'] = idx

                # Any further transformations needed should be done here.

                source_id = _make_source_id(source)
                yield source, source_id
                idx += 1
            self.logger.info("tool-data-indexing: tool {}, json end {}", self.toolname, df['path'])
        return

    def make_source(self):
        """Simple jump method to pick the correct source generator based on the
        handler's prospectus."""
        if not self.files:
            # If we do not have any data files for this tool, ignore it.
            return
        if self.handler['@prospectus']['method'] == 'unify':
            gen = self._make_source_unified()
        elif self.handler['@prospectus']['method'] == 'individual':
            gen = self._make_source_individual()
        elif self.handler['@prospectus']['method'] == 'json':
            gen = self._make_source_json()
        elif self.handler['@prospectus']['method'] == 'periodic_timestamp':
            gen = self._make_source_stdout()
        else:
            raise Exception("Logic bomb!")
        return gen

    @staticmethod
    def get_csv_files(handler, basepath, toolsgroup, tool, ptb):
        """
        Fetch the list of .csv files for this tool, fetch their headers, and
        return a dictionary mapping their column headers to their field names.
        """
        path = os.path.join(basepath, "csv")
        paths = [x for x in ptb.tb.getnames() if x.find(path) >= 0 and ptb.tb.getmember(x).isfile()]
        datafiles = []
        for p in paths:
            fname = os.path.basename(p)
            for rec in handler['patterns']:
                if rec['pattern'].match(fname):
                    handler_rec = rec
                    break
            else:
                # Try an alias
                try:
                    alias_name = _aliases[fname]
                except KeyError:
                    # Ignore .csv files for which we don't have a handler,
                    # after checking to see if they might have an alias
                    # name.
                    #self.logger.warning("no .csv handler for '{}' ({})\n",
                    #        fname, p)
                    continue
                else:
                    for rec in handler['patterns']:
                        if rec['pattern'].match(alias_name):
                            handler_rec = rec
                            break
                    else:
                        # Ignore .csv files for which we don't have a handler
                        #self.logger.warning("no .csv handler for '{}' ({}, {})\n",
                        #        alias_name, fname, p)
                        continue
            assert handler_rec is not None, "Logic bomb! handler_rec is None"
            datafile = _dict_const(path=p, basename=fname, handler_rec=handler_rec)
            datafile['reader'] = reader = csv.reader(open(os.path.join(ptb.extracted_root, p)))
            datafile['header'] = next(reader)
            datafiles.append(datafile)
        return datafiles

    @staticmethod
    def get_json_files(handler, basepath, toolsgroup, tool, ptb):
        """
        Fetch the list of json files for this tool, and return a list of dicts
        containing their metadata.
        """
        path = os.path.join(basepath, "json")
        paths = [x for x in ptb.tb.getnames() if x.find(path) >= 0 and ptb.tb.getmember(x).isfile()]
        datafiles = []
        for p in paths:
            fname = os.path.basename(p)
            datafile = _dict_const(path=p, basename=fname, handler_rec=None)
            datafiles.append(datafile)
        return datafiles

    @staticmethod
    def get_stdout_files(handler, basepath, toolsgroup, tool, ptb):
        """
        Fetch the stdout file for this tool returning a list of dicts
        containing their metadata.
        """
        stdout_file = "{0}-stdout.txt".format(tool)
        path = os.path.join(basepath, stdout_file)
        paths = [x for x in ptb.tb.getnames() if x.find(path) >= 0 and ptb.tb.getmember(x).isfile()]
        datafiles = []
        for p in paths:
            fname = os.path.basename(p)
            handler_rec = None
            for rec in handler['patterns']:
                if rec['pattern'].match(fname):
                    handler_rec = rec
                    break
            if handler_rec is not None:
                datafile = _dict_const(path=p, basename=stdout_file, handler_rec=handler_rec)
                datafiles.append(datafile)
        return datafiles

    @staticmethod
    def get_files(handler, basepath, toolsgroup, tool, ptb):
        if handler is None:
            datafiles = []
        elif handler['@prospectus']['handling'] == 'csv':
            datafiles = ToolData.get_csv_files(handler, basepath, toolsgroup, tool, ptb)
        elif handler['@prospectus']['handling'] == 'json':
            datafiles = ToolData.get_json_files(handler, basepath, toolsgroup, tool, ptb)
        elif handler['@prospectus']['handling'] == 'stdout':
            datafiles = ToolData.get_stdout_files(handler, basepath, toolsgroup, tool, ptb)
        else:
            raise Exception("Logic bomb! %s" % (handler['@prospectus']['handling']))
        datafiles.sort(key=itemgetter('path', 'basename'))
        return datafiles


# tool data are stored in csv files in the tarball.
# the structure is
#      <iterN> -> sampleN -> tools-$group -> <host> -> <tool> -> csv -> files
# we have access routines for getting the iterations, samples, hosts, tools and files
# because although we prefer to get as many of these things out of the metadata log,
# that may not be possible; in the latter case, we fall back to trawling through the
# tarball and using heuristics.

def get_iterations(ptb):
    try:
        # N.B. Comma-separated list
        iterations_str = ptb.run_metadata['iterations']
    except Exception:
        # TBD - trawl through tb with some heuristics
        iterations = []
        for x in ptb.tb.getnames():
            l = x.split('/')
            if len(l) != 2:
                continue
            iter = l[1]
            if re.search('^[1-9][0-9]*-', iter):
                iterations.append(iter)
    else:
        iterations = iterations_str.split(', ')
    iterations_set = set(iterations)
    iterations = list(iterations_set)
    iterations.sort()
    return iterations

def get_samples(ptb, iteration):
    samples = []
    for x in ptb.tb.getnames():
        if x.find("{}/".format(iteration)) < 0:
            continue
        l = x.split('/')
        if len(l) !=  3:
            continue
        sample = l[2]
        if sample.startswith('sample'):
            samples.append(sample)
    if len(samples) == 0:
        samples.append('reference-result')
    samples_set = set(samples)
    samples = list(samples_set)
    samples.sort()
    return samples

def get_hosts(mdconf, logger):
    try:
        # N.B. Space-separated list
        hosts = mdconf.get("tools", "hosts")
    except ConfigParserError:
        logger.exception("ConfigParser error in get_hosts: tool data will"
                " *not* be indexed -- this is most probably a bug: please open"
                " an issue")
        return []
    except NoSectionError:
        logger.warning("No [tools] section in metadata.log: tool data will"
                " *not* be indexed.")
        return []
    except NoOptionError:
        logger.warning("No \"hosts\" option in [tools] section in metadata"
                " log: tool data will *NOT* be indexed.")
        return []
    hosts_set = set(hosts.split())
    hosts = list(hosts_set)
    hosts.sort()
    return hosts

def get_tools(host, mdconf, logger):
    try:
        tools = mdconf.options("tools/{}".format(host))
    except ConfigParserError:
        logger.exception("ConfigParser error in get_tools: tool data will"
                " *not* be indexed -- this is most probably a bug: please open"
                " an issue")
        return []
    except NoSectionError:
        logger.warning("No [tools/{}] section in metadata.log: tool data will"
                " *not* be indexed", host)
        return []
    except NoOptionError:
        logger.warning("No tools in [tools/{}] section in metadata log: tool"
                " data will *NOT* be indexed", host)
        return []
    # Be sure we don't include tool metadata
    tools_list = [ tool for tool in set(tools) \
            if not tool.startswith("remote@") and tool not in ("hostname-s", "label") ]
    tools_list.sort()
    return tools_list

def mk_tool_data(ptb, idxctx):
    iterations = get_iterations(ptb)
    for iteration in iterations:
        samples = get_samples(ptb, iteration)
        for sample in samples:
            hosts = get_hosts(ptb.mdconf, idxctx.logger)
            for host in hosts:
                tools = get_tools(host, ptb.mdconf, idxctx.logger)
                for tool in tools:
                    yield ToolData(ptb, iteration, sample, host, tool, idxctx)
    return

def mk_tool_data_actions(ptb, idxctx):
    for td in mk_tool_data(ptb, idxctx):
        # Each ToolData object, td, that is returned here represents how
        # data collected for that tool across all hosts is to be returned.
        # The make_source method returns a generator that will emit each
        # source document for the appropriate unit of tool data.  Each has
        # the option of constructing that data as best fits its tool data.
        # The tool data for each tool is kept in its own index to allow
        # for different curation policies for each tool.
        asource = td.make_source()
        if not asource:
            continue
        type_name = "pbench-tool-data-{}".format(td.toolname)
        for source, source_id in asource:
            try:
                idx_name = td.generate_index_name('tool-data', source, toolname=td.toolname)
            except BadDate:
                pass
            else:
                action = _dict_const(
                    _op_type=_op_type,
                    _index=idx_name,
                    _type=type_name,
                    _id=source_id,
                    _source=source
                )
                yield action
    return

###########################################################################
# Build tar ball table-of-contents (toc) source documents.

def get_md5sum_of_dir(dir, parentid):
    """Calculate the md5 sum of all the names in the toc"""
    h = hashlib.md5()
    h.update(parentid.encode('utf-8'))
    h.update(dir['directory'].encode('utf-8'))
    if 'files' in dir:
        for f in dir['files']:
            for k in sorted(f.keys()):
                h.update(repr(f[k]).encode('utf-8'))
    return h.hexdigest()

def mk_toc_actions(ptb, idxctx):
    """Construct Table-of-Contents actions.

    These are indexed into the run index along side the runs."""
    tstamp = ptb.start_run
    # Since the timestamp for every TOC record will be the same, we generate
    # the index name once here using a fake source document on the call to
    # generate_index_name().
    pd = PbenchData(ptb, idxctx)
    idx_name = pd.generate_index_name('toc-data', { "@timestamp": tstamp })
    for source in ptb.gen_toc():
        source["@timestamp"] = tstamp
        action = _dict_const(
            _id=get_md5sum_of_dir(source, ptb.run_metadata['id']),
            _op_type=_op_type,
            _index=idx_name,
            _type="pbench-run-toc-entry",
            _source=source,
            _parent=ptb.run_metadata['id']
        )
        yield action
    return

###########################################################################
# Build run source document

# routines for handling sosreports, hostnames, and tools
def valid_ip(address):
    try:
        socket.inet_aton(address)
        return True
    except Exception:
        return False

def search_by_host(sos_d_list, host):
    for sos_d in sos_d_list:
        if host in sos_d.values():
            return sos_d['hostname-f']
    return None

def search_by_ip(sos_d_list, ip):
    # import pdb; pdb.set_trace()
    for sos_d in sos_d_list:
        for l in sos_d.values():
            if type(l) != type([]):
                continue
            for d in l:
                if type(d) != type({}):
                    continue
                if ip in d.values():
                    return sos_d['hostname-f']
    return None

def get_hostname_f_from_sos_d(sos_d, host=None, ip=None):
    if not host and not ip:
        return None

    if host:
        return search_by_host(sos_d, host)
    else:
        return search_by_ip(sos_d, ip)

def mk_tool_info(sos_d, mdconf, logger):
    """Return a dict containing tool info (local and remote)"""
    try:
        tools_array = []

        labels = _dict_const()
        for host in mdconf.get("tools", "hosts").split():
            tools_info = _dict_const()
            # XXX - we should have an FQDN for the host but
            # sometimes we have only an IP address.
            tools_info['hostname'] = host
            # import pdb; pdb.set_trace()
            if valid_ip(host):
                full_hostname = get_hostname_f_from_sos_d(sos_d, ip=host)
            else:
                full_hostname = get_hostname_f_from_sos_d(sos_d, host=host)
            if full_hostname:
                tools_info['hostname-f'] = full_hostname
            section = "tools/{}".format(host)
            items = mdconf.items(section)
            options = mdconf.options(section)
            if 'label' in options:
                tools_info['label'] = mdconf.get(section, 'label')

            # process remote entries for a label and remember them in the labels dict
            remoteitems = [x for x in items if x[0].startswith('remote@') and x[1]]
            for (k,v) in remoteitems:
                host = k.replace('remote@', '', 1)
                labels[host] = v

            # now, forget about any label or remote entries - they have been dealt with.
            items = [x for x in items if x[0] != 'label' and not x[0].startswith('remote')]

            tools = _dict_const()
            tools.update(items)
            try:
                hostname_s = tools['hostname-s']
            except KeyError:
                pass
            else:
                # Move the tool/host "hostname-s" value to the tools_info level.
                if tools_info['hostname'] != hostname_s:
                    tools_info['hostname-s'] = hostname_s
                del tools['hostname-s']
            tools_info['tools'] = tools
            tools_array.append(tools_info)

        # now process remote labels
        for item in tools_array:
            host = item['hostname']
            if host in labels:
                item['label'] = labels[host]

        return tools_array

    except Exception:
        logger.exception("mk_tool_info")
        return []

def ip_address_to_ip_o_addr(s):
    # This routine deals with the contents of either the ip_-o_addr
    # (preferred) or the ip_address file in the sosreport.
    # If each line starts with a number followed by a colon,
    # leave it alone and return it as is - that's the preferred case.
    # If not, grovel through the ip_address file, collect the juicy pieces
    # and fake a string that is similar in format to the preferred case -
    # at least similar enough to satisfy the caller of this function.
    as_is = True
    pat = re.compile(r'^[0-9]+:')

    # reduce is not available in python3 :-(
    # as_is = reduce(lambda x, y: x and y,
    #               map(lambda x: re.match(pat, x), s.split('\n')[:-1]))
    for l in s.split('\n')[:-1]:
        if not re.match(pat, l):
            as_is = False
            break
    if as_is:
        return s

    # rats - we've got to do real work
    # state machine
    # start: 0
    # seen <N:>: 1
    # seen inet* : 2
    # EOF: 3
    # if we see anything else, we stay put in the current state
    # transitions: 2 --> 1  action: output a line
    #              2 --> 2  action: output a line
    #
    state = 0
    ret = ""
    # import pdb; pdb.set_trace()
    for l in s.split('\n'):
        if re.match(pat, l):
            if state == 0 or state == 1:
                state = 1
            elif state == 2:
                ret += "%s: %s %s %s\n" % (serial, ifname, proto, addr)
                state = 1
            serial, ifname = l.split(':')[0:2]
        elif l.lstrip().startswith('inet'):
            assert(state != 0), \
                    "Logic bomb! Unexpected state: {!r}".format(state)
            if state == 1:
                state = 2
            elif state == 2:
                ret += "%s: %s %s %s\n" % (serial, ifname, proto, addr)
                state = 2
            proto, addr = l.lstrip().split()[0:2]
    if state == 2:
        ret += "%s: %s %s %s\n" % (serial, ifname, proto, addr)
        state = 3
    return ret

def if_ip_from_sosreport(ip_addr_f):
    """Parse the ip_-o_addr file or ip_address file from the sosreport and
    get a dict associating the if name with the ip - separate entries
    for inet and inet6.
    """

    s = str(ip_addr_f.read(), 'iso8859-1')
    d = _dict_const()
    # if it's an ip_address file, convert it to ip_-o_addr format
    s = ip_address_to_ip_o_addr(s)
    for l in s.split('\n'):
        fields = l.split()
        if not fields:
            continue
        ifname = fields[1]
        ifproto = fields[2]
        ifip = fields[3].split('/')[0]
        if ifproto not in d:
            d[ifproto] = []
        d[ifproto].append(_dict_const(ifname=ifname, ipaddr=ifip))

    return d

def find_hostname(a_string):
    ret_val = a_string.find('sos_commands/host/hostname')
    if ret_val < 0:
        ret_val = a_string.find('sos_commands/general/hostname')
    return ret_val

def hostnames_if_ip_from_sosreport(sos_file_name):
    """Return a dict with hostname info (both short and fqdn) and
    ip addresses of all the network interfaces we find at sosreport time."""

    sostb = tarfile.open(sos_file_name)
    hostname_files = [x for x in sostb.getnames() if find_hostname(x) >= 0]

    # Fetch the hostname -f and hostname file contents
    hostname_f_file = [x for x in hostname_files if x.endswith('hostname_-f')]
    if hostname_f_file:
        try:
            hostname_f = str(sostb.extractfile(hostname_f_file[0]).read(), 'iso8859-1')[:-1]
        except IOError as e:
            raise SosreportHostname("Failure to fetch a hostname-f from the sosreport")
        if hostname_f == 'hostname: Name or service not known':
            hostname_f = ""
    else:
        hostname_f = ""
    hostname_s_file = [x for x in hostname_files if x.endswith('hostname')]
    if hostname_s_file:
        try:
            hostname_s = str(sostb.extractfile(hostname_s_file[0]).read(), 'iso8859-1')[:-1]
        except IOError as e:
            raise SosreportHostname("Failure to fetch a hostname from the sosreport")
    else:
        hostname_s = ""

    if not hostname_f and not hostname_s:
        raise SosreportHostname("We do not have a hostname recorded in the sosreport")

    # import pdb; pdb.set_trace()
    if hostname_f and hostname_s:
        if hostname_f == hostname_s:
            # Shorten the hostname if possible
            hostname_s = hostname_f.split('.')[0]
        elif hostname_f.startswith(hostname_s):
            # Already have a shortened hostname
            pass
        elif hostname_s.startswith(hostname_f):
            # switch them
            x = hostname_s
            hostname_s = hostname_f
            hostname_f = x
        elif hostname_f != "localhost":
            hostname_s = hostname_f.split('.')[0]
        elif hostname_s != "localhost":
            hostname_f = hostname_s
        else:
            raise SosreportHostname("Can't reconcile short and full hostname")

    elif not hostname_f and hostname_s:
        # The sosreport did not include, or failed to properly collect, the
        # output from "hostname -f", so we'll just keep them the same
        hostname_f = hostname_s
        # Shorten the hostname if possible
        hostname_s = hostname_f.split('.')[0]
    elif hostname_f and not hostname_s:
        # Shorten the hostname if possible
        hostname_s = hostname_f.split('.')[0]
    else:
        # both undefined
        raise SosreportHostname("Hostname undefined (both short and long)")

    if hostname_f == "localhost" and hostname_s != "localhost":
        hostname_f = hostname_s
        hostname_s = hostname_f.split('.')[0]
    elif hostname_f != "localhost" and hostname_s == "localhost":
        hostname_s = hostname_f.split('.')[0]
    elif hostname_f == "localhost" and hostname_s == "localhost":
        raise SosreportHostname("The sosreport did not collect a hostname other than 'localhost'")
    else:
        pass

    d = _dict_const([
        ('hostname-f', hostname_f),
        ('hostname-s', hostname_s)
    ])

    # get the ip addresses for all interfaces
    ipfiles = [x for x in sostb.getnames() if x.find('sos_commands/networking/ip_') >= 0]
    ip_files = [x for x in ipfiles if x.find('sos_commands/networking/ip_-o_addr') >= 0]
    if ip_files:
        d.update(if_ip_from_sosreport(sostb.extractfile(ip_files[0])))
    else:
        # try the ip_address file instead
        ip_files = [x for x in ipfiles if x.find('sos_commands/networking/ip_address') >= 0]
        if ip_files:
            d.update(if_ip_from_sosreport(sostb.extractfile(ip_files[0])))
    return d

def mk_sosreports(tb, extracted_root, logger):
    sosreports = [ x for x in tb.getnames() if x.find("sosreport") >= 0 and x.endswith('.md5') ]
    sosreports.sort()

    sosreportlist = []
    for x in sosreports:
        # x is the *sosreport*.tar.xz.md5 filename
        sos = x[:x.rfind('.md5')]
        md5f = os.path.join(extracted_root, x)
        try:
            with open(md5f, "r") as fp:
                md5_val = fp.read()[:-1]
        except Exception as e:
            logger.warning("Failed to fetch .md5 of sosreport {}: {}", sos, e)
            continue
        host_md = hostnames_if_ip_from_sosreport(os.path.join(extracted_root, sos))
        # get hostname (short and FQDN) from sosreport
        d = _dict_const()
        d['name'] = sos
        d['md5'] = md5_val
        d.update(host_md)
        sosreportlist.append(d)

    return sosreportlist

def mk_user_specified_metadata(idxctx):
    # parse the JSON string into a dict and return it
    try:
        return json.loads(idxctx.options.metadata_string)
    except Exception:
        logger.exception("Cannot parse user specified metadata JSON string:"
                " {}\n", idxctx.options.metadata_string)
        return {}

def mk_run_action(ptb, idxctx):
    """Extract metadata from the named tarball and create an indexing
       action out of them.

       There are two kinds of metadata: what goes into _source[@metadata]
       is metadata about the tarball itself - not things that are *part* of
       the tarball: its name, size, md5, mtime, etc.  Metadata about the run
       are *data* to be indexed under the "run" field.
    """
    source = _dict_const([('@timestamp', ptb.start_run)])

    # debug: -T options will cause each call below to be timed
    # and the elapsed interval printed.
    debug_time_operations = idxctx.options.debug_time_operations
    source['@metadata'] = ptb.at_metadata
    source['run'] = ptb.run_metadata
    if idxctx.options.metadata_string:
        if debug_time_operations: _ts("mk_user_specified_metadata")
        source['user_specified_metadata'] = mk_user_specified_metadata(idxctx)
    if debug_time_operations: _ts("mk_sosreports")
    sos_d = mk_sosreports(ptb.tb, ptb.extracted_root, idxctx.logger)
    if sos_d:
        source['sosreports'] = sos_d
    if debug_time_operations: _ts("mk_tool_info")
    source['host_tools_info'] = mk_tool_info(sos_d, ptb.mdconf, idxctx.logger)

    # make a simple action for indexing
    pd = PbenchData(ptb, idxctx)
    idx_name = pd.generate_index_name('run-data', source)
    action = _dict_const(
        _op_type=_op_type,
        _index=idx_name,
        _type="pbench-run",
        _id=ptb.run_metadata['id'],
        _source=source,
    )
    if debug_time_operations: _ts("Done!", newline=True)
    return action

def make_all_actions(ptb, idxctx):
    """Driver for generating all actions on source documents for indexing
    into Elasticsearch. This generator drives the generation of the run
    source document, the table-of-contents tar ball documents, and finally
    all the tool data.
    """
    debug_time_operations = idxctx.options.debug_time_operations
    if debug_time_operations: _ts("mk_run_action")
    yield mk_run_action(ptb, idxctx)
    if debug_time_operations: _ts("mk_toc_actions")
    for action in mk_toc_actions(ptb, idxctx):
        yield action
    if debug_time_operations: _ts("mk_result_data_actions")
    for action in mk_result_data_actions(ptb, idxctx):
        yield action
    if debug_time_operations: _ts("mk_tool_data_actions")
    for action in mk_tool_data_actions(ptb, idxctx):
        yield action
    if debug_time_operations: _ts("mk_all_actions-done", newline=True)
    return


class PbenchTarBall(object):
    def __init__(self, idxctx, tbarg, tmpdir):
        self.idxctx = idxctx
        self.tbname = tbarg
        self.controller_dir = os.path.basename(os.path.dirname(self.tbname))
        try:
            self.satellite, self.controller_name = self.controller_dir.split("::", 1)
        except Exception:
            self.satellite = None
            self.controller_name = self.controller_dir
        tb_stat = os.stat(self.tbname)
        mtime = datetime.utcfromtimestamp(tb_stat.st_mtime)
        self.tb = tarfile.open(self.tbname)

        # This is the top-level name of the run - it should be the common
        # first component of every member of the tarball.
        dirname = os.path.basename(self.tbname)
        self.dirname = dirname[:dirname.rfind('.tar.xz')]
        # ... but let's make sure ...
        #
        # ... while we are at it, we verify we have a metadata.log file in the
        # tar ball before we start extracting.
        metadata_log_path = "%s/metadata.log" % (self.dirname)
        metadata_log_found = False
        self.members = self.tb.getmembers()
        for m in self.members:
            if m.name == metadata_log_path:
                metadata_log_found = True
            sampled_prefix = m.name.split(os.path.sep)[0]
            if sampled_prefix != self.dirname:
                # All members of the tarball should have self.dirname as its
                # prefix.
                raise UnsupportedTarballFormat(
                    "{} - directory prefix should be \"{}\", but is"
                    " \"{}\" instead, for tarball member \"{}\"".format(
                        self.tbname,
                        self.dirname,
                        sampled_prefix,
                        m.name))
        if not metadata_log_found:
            raise UnsupportedTarballFormat(
                "{} - tarball is missing \"{}\".".format(
                    self.tbname, metadata_log_path))

        # We are expected to clean up the extracted tar ball before we exit.
        self.extracted_root = tmpdir
        self.tb.extractall(path=self.extracted_root)
        if not os.path.isdir(os.path.join(self.extracted_root, self.dirname)):
            self.delete_extracted()
            raise UnsupportedTarballFormat(
                "{} - extracted tarball but can't get to the directory \"{}\".".format(
                    self.tbname,
                    os.path.join(self.extracted_root, self.dirname)))
        # Open the MD5 file of the tarball and read the MD5 sum from it.
        md5sum = open("%s.md5" % (self.tbname)).read().split()[0]
        # Construct the @metadata and run metadata dictionaries from the
        # metadata.log file.
        self.mdconf = ConfigParser()
        mdf = os.path.join(self.extracted_root, metadata_log_path)
        try:
            # Read and parse the metadata.log file.
            self.mdconf.read(mdf)
            controller = self.mdconf.get('run', 'controller')
            if not controller:
                raise Exception("empty run.controller")
            if not controller.startswith(self.controller_name):
                raise Exception("run.controller (\"{}\") does not match"
                        " controller_dir (\"{}\")".format(
                        controller, self.controller_dir))
            name = self.mdconf.get('pbench', 'name')
            if not name:
                raise Exception("empty pbench.name")
            script = self.mdconf.get('pbench', 'script')
            if not script:
                raise Exception("empty pbench.script")
            toolsgroup = self.mdconf.get("tools", "group")
            if not toolsgroup:
                raise Exception("empty tools.group")
            # Fetch the original run date values from the metadata.log file.
            # The goal is to provide self.start_run and self.end_run fields
            # containing strings of the form, "YYYY-mm-ddTHH:MM:SS.ssssss",
            # and then self.start_run_ts and self.end_run_ts with datetime
            # objects derived from those strings.
            start_run_orig = self.mdconf.get('run', 'start_run')
            if not start_run_orig:
                raise Exception("empty run.start_run")
            end_run_orig = self.mdconf.get('run', 'end_run')
            if not end_run_orig:
                raise Exception("empty run.end_run")
            date_orig = self.mdconf.get('pbench', 'date')
            if not date_orig:
                raise Exception("empty pbench.date")
        except Exception as e:
            self.delete_extracted()
            raise BadMDLogFormat("{} - error fetching required metadata.log"
                    " fields, \"{}\"".format(self.tbname, e))
        # Normalize all the timestamps
        self.start_run_ts, self.start_run = PbenchTarBall.convert_to_dt(start_run_orig)
        self.end_run_ts, self.end_run = PbenchTarBall.convert_to_dt(end_run_orig)
        date_ts, date = PbenchTarBall.convert_to_dt(date_orig)
        # At this point, date is a local time value, while start_ and
        # end_run are UTC.  We figure out what the UTC offset is by
        # comparing date to the start run value, and adjusting it
        # accordingly.  Since these are supposed to be close, we calculate
        # an offset rounded to a half-hour and add it to the local
        # date. We then convert back to an ISO format date.
        offset = date_ts - self.start_run_ts
        res = round(((float(offset.seconds) / 60) / 60) + (offset.days * 24), 1)
        date_ts -= timedelta(0, int(res * 60 * 60), 0)
        date = date_ts.isoformat()
        # The pbench tar balls metadata.log file has two sections, "pbench"
        # and "run" that we merge together and fix up.  We first pull the
        # "pbench.rpm-version" field into the "@metadata" section, and then we
        # pull the "run.prefix" in as "@metadata.result-prefix".
        self.at_metadata = _dict_const([
                ('file-date', mtime.isoformat()),
                ('file-name', self.tbname),
                ('file-size', tb_stat.st_size),
                ('generated-by', _NAME_),
                ('generated-by-version', _VERSION_),
                ('md5', md5sum),
                ('toc-prefix', self.dirname)
            ])
        try:
            rpm_version = self.mdconf.get("pbench", "rpm-version")
        except NoOptionError:
            pass
        else:
            self.at_metadata['pbench-agent-version'] = rpm_version
        try:
            result_prefix = self.mdconf.get("run", "prefix")
        except NoOptionError:
            pass
        else:
            self.at_metadata['result-prefix'] = result_prefix
        if self.satellite is not None:
            self.at_metadata['satellite'] = self.satellite
        self.at_metadata['controller_dir'] = self.controller_dir
        # Merge the "pbench" and "run" sections of the metadata.log file into
        # the "run" metadata, removing the "rpm-version" previously pulled.
        self.run_metadata = _dict_const()
        try:
            self.run_metadata.update(self.mdconf.items('run'))
            self.run_metadata.update(self.mdconf.items('pbench'))
        except NoSectionError as e:
            raise BadMDLogFormat(
                    "{} - missing section in metadata.log, \"{}\"".format(
                        self.dirname, e))
        # Remove from run metadata as these fields are either kept in
        # @metadata or being renamed.
        for key in ( 'rpm-version', 'prefix', 'start_run', 'end_run' ):
            try:
                del self.run_metadata[key]
            except KeyError:
                pass
        # Remove any optional empty fields (all required fields have already
        # been determined as present.
        for key in list(self.run_metadata.keys()):
            if len(self.run_metadata[key]) == 0:
                del self.run_metadata[key]
        # Add the tools group used as run metadata for indexing purposes.
        self.run_metadata['toolsgroup'] = toolsgroup
        # Update the start and end run times using the already updated
        # values in the tar ball object.
        self.run_metadata['start'] = self.start_run
        self.run_metadata['end'] = self.end_run
        self.run_metadata['date'] = date
        # The run id here is the md5sum that's the _id of the main document.
        # It's what ties all of the relevant documents together.
        self.run_metadata['id'] = md5sum

    # We'll accept dates that match any of the following:
    #  * 2019-01-10_12:12:12
    #  * 2019-01-10T12:12:12
    #  * 20190110_12:12:12
    #  * 20190110T12:12:12
    #  * 2019-01-10_12:12:12.123456[789]
    #  * 2019-01-10T12:12:12.123456[789]
    #  * 20190110_12:12:12.123456[789]
    #  * 20190110T12:12:12.123456[789]
    # However, we reduce the combinations by immediately replacing the
    # "_" version with a "T", and ensure we only keep microseconds of
    # resolution, dropping any extra nanoseconds because that level of
    # precision is ignored and causes problems during date/time string
    # conversions (e.g. Elasticsearch ignores it, and python std lib
    # does not offer a way to handle nanoseconds).
    _formats = [ "%Y-%m-%dT%H:%M:%S.%f", "%Y%m%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y%m%dT%H:%M:%S" ]

    @staticmethod
    def convert_to_dt(dt_str):
        rts = dt_str.replace('_', 'T')
        us_offset = rts.rfind('.')
        us = rts[us_offset:][:7]
        rts = rts[:us_offset] + us
        for f in PbenchTarBall._formats:
            try:
                dt = datetime.strptime(rts, f)
            except ValueError:
                continue
            else:
                return dt, dt.isoformat()
        else:
            raise Exception()

    _mode_table = _dict_const([
        (tarfile.REGTYPE, "reg"),
        (tarfile.AREGTYPE, "areg"),
        (tarfile.LNKTYPE, "lnk"),
        (tarfile.SYMTYPE, "sym"),
        (tarfile.DIRTYPE, "dir"),
        (tarfile.FIFOTYPE, "fifo"),
        (tarfile.CONTTYPE, "cont"),
        (tarfile.CHRTYPE, "chr"),
        (tarfile.BLKTYPE, "blk"),
        (tarfile.GNUTYPE_SPARSE, "spr")
        ])

    def gen_toc(self):
        """Generate (t)able (o)f (c)ontents JSON documents for this tarball.

        There should be one JSON document emitted per directory entry found in
        the tarball. Each non-directory entry found is added to the given
        directory entry it belongs. This is determined by the name element
        which is always the full path of the object in the tar ball.

        So given a tar file that looks like
        <prefix = "pbench-user-benchmark_ex-tb_2018.10.24T14.38.18">:

        drwxr-xr-x root/root         0 2018-10-24 10:58:00 <prefix>/
        drwxr-xr-x root/root         0 2018-10-24 10:38:01 <prefix>/1/
        drwxr-xr-x root/root         0 2018-10-24 10:58:02 <prefix>/1/rr/
        drwxr-xr-x root/root         0 2018-10-24 10:58:03 <prefix>/1/rr/td/
        drwxr-xr-x root/root         0 2018-10-24 10:58:04 <prefix>/1/rr/td/host.example.com/
        drwxr-xr-x root/root         0 2018-10-24 10:58:05 <prefix>/1/rr/td/host.example.com/iostat/
        -rwxr-xr-x root/root        48 2018-10-24 10:38:06 <prefix>/1/rr/td/host.example.com/iostat/iostat.cmd
        -rw-r--r-- root/root      7598 2018-10-24 10:58:07 <prefix>/1/rr/td/host.example.com/iostat/iostat-stdout.txt
        drwxr-xr-x root/root         0 2018-10-24 10:58:08 <prefix>/1/rr/td/host.example.com/iostat/csv/
        -rw-r--r-- root/root       512 2018-10-24 10:58:09 <prefix>/1/rr/td/host.example.com/iostat/csv/disk_IOPS.csv
        -rw-r--r-- root/root       512 2018-10-24 10:58:10 <prefix>/1/rr/td/host.example.com/iostat/csv/disk_Wait_Time_msec.csv
        -rw-r--r-- root/root       382 2018-10-24 10:58:11 <prefix>/1/rr/td/host.example.com/iostat/disk-average.txt
        -rw-r--r-- root/root      1379 2018-10-24 10:58:12 <prefix>/1/rr/td/host.example.com/iostat/disk.html

        This method should emit JSON documents that look like:

        { "directory": "/",                                       "mode": 0o755, "mtime": "2018-10-24T10:58:01" }
        { "directory": "/1/",                                     "mode": 0o755, "mtime": "2018-10-24T10:38:01" }
        { "directory": "/rr/",                                    "mode": 0o755, "mtime": "2018-10-24T10:58:02" }
        { "directory": "/rr/td/",                                 "mode": 0o755, "mtime": "2018-10-24T10:58:03" }
        { "directory": "/rr/td/host.example.com/",                "mode": 0o755, "mtime": "2018-10-24T10:58:04" }
        { "directory": "/rr/td/host.exmaple.com/iostat/",         "mode": 0o755, "mtime": "2018-10-24T10:58:05",
            "files": [
                { "name": "iostat.cmd",             "size":   48, "mode": 0o755, "mtime": "2018-10-24T10:38:06" },
                { "name": "iostat-stdout.txt",      "size": 7598, "mode": 0o644, "mtime": "2018-10-24T10:58:07" },
                { "name": "disk-average.txt",       "size":  382, "mode": 0o644, "mtime": "2018-10-24T10:58:11" },
                { "name": "disk.html",              "size": 1379, "mode": 0o644, "mtime": "2018-10-24T10:58:12" }
            ] }
        { "directory": "/rr/td/host.exmaple.com/iostat/csv/",     "mode": 0o755, "mtime": "2018-10-24T10:58:08",
            "files": [
                { "name": "disk_IOPS.csv",           "size": 512, "mode": 0o644, "mtime": "2018-10-24T10:58:09" },
                { "name": "disk_Wait_Time_msec.csv", "size": 512, "mode": 0o644, "mtime": "2018-10-24T10:58:10" }
            ] }

        """
        prefix_l = len(self.dirname)
        # Note we have to fully populate the dictionary by processing all the
        # members before we can yield the generated sources for each
        # directory.
        toc_dirs = _dict_const()
        for m in self.members:
            # Always strip the prefix
            name = m.name[prefix_l:]
            if m.isdir():
                dname = name if name.endswith(os.path.sep) else "{}{}".format(
                    name, os.path.sep)
                if dname in toc_dirs:
                    raise Exception("Logic bomb! Found a directory entry that"
                            " already exists!")
                toc_dirs[dname] = _dict_const(
                        directory=dname,
                        mtime=datetime.utcfromtimestamp(float(m.mtime)).isoformat(),
                        mode=oct(m.mode)
                    )
            else:
                fentry = _dict_const(
                        name=os.path.basename(name),
                        mtime=datetime.utcfromtimestamp(float(m.mtime)).isoformat(),
                        size=m.size,
                        mode=oct(m.mode)
                )
                try:
                    ftype = self._mode_table[m.type]
                except KeyError:
                    ftype = "unk"
                fentry['type'] = ftype
                if m.issym():
                    fentry['linkpath'] = m.linkpath
                dname = os.path.dirname(name)
                if not dname.endswith(os.path.sep):
                    dname = "{}{}".format(dname, os.path.sep)
                # we may have created an empty dir entry already without a
                # 'files' entry, so we now make sure that there is an
                # empty 'files' entry that we can populate.
                if 'files' not in toc_dirs[dname]:
                    toc_dirs[dname]['files'] = []
                toc_dirs[dname]['files'].append(fentry)
        for key in sorted(toc_dirs.keys()):
            source = toc_dirs[key]
            try:
                sorted_file_list = sorted(source['files'], key=itemgetter('name', 'mtime'))
            except KeyError:
                pass
            else:
                source['files'] = sorted_file_list
            yield source

    def delete_extracted(self):
        directory = os.path.join(self.extracted_root, self.dirname)
        if not os.path.exists(directory):
            return
        def remove_readonly(func, path, _):
            "Clear the readonly bit and reattempt the removal"
            os.chmod(path, stat.S_IWRITE)
            func(path)
        shutil.rmtree(directory, onerror=remove_readonly)


class IdxContext(object):
    """
    The general indexing options, including configuration and other external
    state, provided as an object.
    """
    def __init__(self, options, _dbg=0):
        self.options = options
        self._dbg = _dbg
        self.opctx = []
        self.config = PbenchConfig(options.cfg_name)
        try:
            self.idx_prefix = self.config.get('Indexing', 'index_prefix')
        except Exception as e:
            raise ConfigFileError(str(e))
        else:
            if '.' in self.idx_prefix:
                raise ConfigFileError("Index prefix, '{}', not allowed to"
                        " contain a period ('.')".format(self.idx_prefix))

        if self.config._unittests:
            import collections
            global _dict_const
            _dict_const = collections.OrderedDict
            def _do_time():
                return 0
            self.time = _do_time
        else:
            self.time = time.time
        self.TS = self.config.TS

        self.logger = get_pbench_logger(_NAME_, self.config)
        self.es = get_es(self.config, self.logger)
        self.templates = PbenchTemplates(os.path.dirname(os.path.abspath(
            sys.argv[0])), self.idx_prefix, self.logger, _known_tool_handlers,
            _dbg=_dbg)

    def dump_opctx(self):
        dump = False
        for ctx in self.opctx:
            if ctx['counters']:
                dump = True
        if dump:
            self.logger.error("** Errors encountered while indexing: {}",
                    json.dumps(self.opctx, sort_keys=True))

def _count_lines(fname):
    try:
        with open(fname, "r") as fp:
            cnt = sum(1 for line in fp)
    except _filenotfounderror:
        cnt = 0
    return cnt

def main(options):
    """Main entry point to pbench-index()

       The caller is required to pass the "options" argument with the following
       expected attributes:
           cfg_name              - Name of the configuration file to use
           dump_index_patterns   - Don't do any indexing, but just emit the
                                   list of index patterns that would be used
           debug_time_operations - Emit timing information for various steps
                                   during execution
       All exceptions are caught and logged to syslog with the stacktrace of
       the exception in an sub-object of the logged JSON document.

       Status codes used by es_index and the error below are defined from the
       list below to maintain compatibility with the previous code base when
       pbench-index was a bash script and invoked index-pbench (yes, a bit
       confusing), the predecessor to this program.  The codes were used to
       sort the errors we encountered processing tar balls in to categories
       of retry or not:

            0 - normal, successful exit, no errors
            1 - Operational error while indexing
            2 - Configuration file not specified
            3 - Bad configuration file
            4 - Tar ball does not contain a metadata.log file
            5 - Bad start run date value encountered
            6 - File Not Found error
            7 - Bad metadata.log file encountered
            8 - Error reading a mapping file for Elasticsearch templates
            9 - Error creating one of the Elasticsearch templates
           10 - Bad hostname in a sosreport
           11 - Failure unpacking the tar ball
           12 - generic error, needs to be investigated and can be retried after
                any indexing bugs are fixed.

       Return Values (now a sub-set of the original status codes above):
         0 - Successfully processed all tar balls (errors processing tar
             balls are reported in the logs and in index status reports)
         1 - Failed to process one or more tar balls for unknown reasons
             (see logs)
         2 - Missing configuration file
         3 - Invalid configuration file
         8 - Unable to load and process expected mapping files
         9 - Unable to update index templates in configured Elasticsearch
             instance
    """
    if not options.cfg_name:
        print("{}: ERROR: No config file specified; set CONFIG env variable or"
                " use --config <file> on the command line".format(_NAME_),
                file=sys.stderr)
        return 2

    idxctx = None
    try:
        idxctx = IdxContext(options, _dbg=_DEBUG)
    except (ConfigFileError, ConfigParserError):
        print("{}: {}".format(_NAME_, e), file=sys.stderr)
        return 2
    except BadConfig as e:
        print("{}: {}".format(_NAME_, e), file=sys.stderr)
        return 3
    except JsonFileError as e:
        print("{}: {}".format(_NAME_, e), file=sys.stderr)
        return 8

    if options.dump_index_patterns:
        idxctx.templates.dump_idx_patterns()
        return 0

    if options.dump_templates:
        idxctx.templates.dump_templates()
        return 0

    res = 0
    try:
        ARCHIVE_rp = os.path.realpath(idxctx.config.ARCHIVE)
        if not os.path.isdir(ARCHIVE_rp):
            idxctx.logger.error("{}: Bad ARCHIVE={}", _NAME_, idxctx.config.ARCHIVE)
            res = 3
        qdir = idxctx.config.get('pbench-server', 'pbench-quarantine-dir')
        if not os.path.isdir(qdir):
            idxctx.logger.error("{}: {} does not exist, or is not a directory", _NAME_, qdir)
            res = 3
    except Exception:
        idxctx.logger.exception("{}: Unexpected setup error", _NAME_)
        res = 12

    if res != 0:
        # Exit early if we encounter any errors.
        return res

    idxctx.logger.info("{}.{}: starting", _NAME_, idxctx.TS)

    # find -L $ARCHIVE/*/$linksrc -name '*.tar.xz' -printf "%s\t%p\n" 2>/dev/null | sort -n > $list
    tarballs = []
    try:
        for tb in glob.iglob(os.path.join(ARCHIVE_rp, "*", _linksrc, "*.tar.xz")):
            try:
                rp = os.path.realpath(tb)
            except OSError:
                idxctx.logger.warning("{} does not resolve to a real path", tb)
                quarantine(qdir, idxctx.logger, tb)
                continue
            controller_path = os.path.dirname(rp)
            archive_path = os.path.dirname(controller_path)
            if archive_path != ARCHIVE_rp:
                idxctx.logger.warning("For tarball {}, original home is not {}", tb, ARCHIVE_rp)
                quarantine(qdir, idxctx.logger, tb)
                continue
            if not os.path.isfile(rp + ".md5"):
                idxctx.logger.warning("Missing .md5 file for {}", tb)
                quarantine(qdir, idxctx.logger, tb)
                # Audit should pick up missing .md5 file in ARCHIVE directory.
                continue
            try:
                # get size
                size = os.path.getsize(rp)
            except OSError:
                idxctx.logger.warning("Could not fetch tar ball size for {}", tb)
                quarantine(qdir, idxctx.logger, tb)
                # Audit should pick up missing .md5 file in ARCHIVE directory.
                continue
            else:
                tarballs.append( (size, tb) )
    except Exception:
        idxctx.logger.exception("Unexpected error encountered generating list of tar"
                " balls to process")
        return 12
    else:
        if not tarballs:
            idxctx.logger.info("No tar balls found that need processing")
            return 0

    tarballs = sorted(tarballs)

    # At this point, tarballs contains a list of tar balls sorted by size
    # that were available as symlinks in the various _linksrc directories.
    idxctx.logger.debug("Preparing to index {:d} tarballs", len(tarballs))

    try:
        # Now that we are ready to begin the actual indexing step, ensure we
        # have the proper index templates in place.
        if options.debug_time_operations: _ts("es_template")
        idxctx.templates.update_templates(idxctx.es)
    except TemplateError as e:
        idxctx.logger.error(repr(e))
        res = 9
    except Exception:
        idxctx.logger.exception("Unexpected template processing error")
        res = 12
    else:
        res = 0

    if res != 0:
        # Exit early if we encounter any errors.
        return res

    with tempfile.TemporaryDirectory(prefix="pbench-index.", dir=idxctx.config.TMP) as tmpdir:
        try:
            with open(os.path.join(tmpdir, "{}.{}.list".format(_NAME_, idxctx.TS)), "w") as lfp:
                # Write out all the tar balls we are processing so external
                # viewers can follow along from home.
                for size, tb in tarballs:
                    print("{:20d} {}".format(size, tb), file=lfp)

            indexed = os.path.join(tmpdir, "{}.{}.indexed".format(_NAME_, idxctx.TS))
            erred   = os.path.join(tmpdir, "{}.{}.erred"  .format(_NAME_, idxctx.TS))
            skipped = os.path.join(tmpdir, "{}.{}.skipped".format(_NAME_, idxctx.TS))

            if idxctx.options.indexing_errors:
                ie_filename = idxctx.options.indexing_errors
            else:
                ie_filename = os.path.join(tmpdir, "{}.{}.indexing-errors.json".format(_NAME_, idxctx.TS))

            for size, tb in tarballs:
                # Sanity check source tar ball path
                linksrc_dir = os.path.dirname(tb)
                linksrc_dirname = os.path.basename(linksrc_dir)
                assert linksrc_dirname == _linksrc, "Logic bomb!  tar ball path {} does not contain {}".format(tb, _linksrc)

                idxctx.logger.info("Starting {} (size {:d})", tb, size)

                if options.debug_time_operations: _ts("index {} ({:d} bytes)".format(tb, size))
                ptb = None
                try:
                    # "Open" the tar ball represented by the tar ball object
                    ptb = PbenchTarBall(idxctx, os.path.realpath(tb), tmpdir)

                    # Construct the generator for emitting all actions.  The `idxctx`
                    # dictionary is passed along to each generator so that it can add its
                    # context for error handling to the list.
                    if options.debug_time_operations: _ts("generator setup")
                    actions = make_all_actions(ptb, idxctx)

                    # File name for containing all indexing errors that
                    # can't/won't be retried.
                    with open(ie_filename, "w") as fp:
                        if options.debug_time_operations: _ts("es_index")
                        es_res = es_index(idxctx.es, actions, fp, idxctx.logger, idxctx._dbg)
                except UnsupportedTarballFormat as e:
                    idxctx.logger.error("Unsupported Tarball Format: {}", e)
                    tb_res = 4
                except BadDate as e:
                    idxctx.logger.error("Bad Date: {!r}", e)
                    tb_res = 5
                except _filenotfounderror as e:
                    idxctx.logger.error("No such file: {}", e)
                    tb_res = 6
                except BadMDLogFormat as e:
                    idxctx.logger.error("The metadata.log file is curdled in tarball: {}", e)
                    tb_res = 7
                except SosreportHostname as e:
                    idxctx.logger.error("Bad hostname in sosreport: {}", e)
                    tb_res = 10
                except tarfile.TarError as e:
                    idxctx.logger.error("Can't unpack tarball into {}: {}", ptb.extracted_root, e)
                    tb_res = 11
                except Exception as e:
                    idxctx.logger.exception("Other indexing error: {}", e)
                    tb_res = 12
                else:
                    beg, end, successes, duplicates, failures, retries = es_res
                    idxctx.logger.info("done indexing (end ts: {}, duration: {:.2f}s,"
                            " successes: {:d}, duplicates: {:d}, failures: {:d},"
                            " retries: {:d})", tstos(end), end - beg, successes,
                            duplicates, failures, retries)
                    tb_res = 1 if failures > 0 else 0
                finally:
                    if ptb:
                        ptb.delete_extracted()
                try:
                    ie_len = os.path.getsize(ie_filename)
                except _filenotfounderror:
                    # Above operation never made it to actual indexing, ignore.
                    pass
                except Exception:
                    idxctx.logger.exception("Unexpected error handling"
                            " indexing errors file: {}", ie_filename)
                else:
                    # Success fetching indexing error file size.
                    if ie_len > len(tb) + 1:
                        report_status(idxctx.es, idxctx.logger,
                                idxctx.config.LOGSDIR, idxctx.idx_prefix,
                                '.'.join(_NAME_, "errors"), tstos(end),
                                "status", ie_filename)
                finally:
                    # Unconditionally remove the indexing errors file.
                    try:
                        os.remove(ie_filename)
                    except Exception:
                        pass
                # Distinguish failure cases, so we can retry the indexing
                # easily if possible.  Different WONT-INDEX directories for
                # different failures; the rest are going to end up in
                # WONT-INDEX for later retry.
                controller_path = os.path.dirname(linksrc_dir)

                if tb_res == 0:
                    idxctx.logger.info("{}: {}/{}: success", idxctx.TS, os.path.basename(controller_path), os.path.basename(tb))
                    # Success
                    with open(indexed, "a") as fp:
                        print(tb, file=fp)
                    _rename_tb_link(tb, os.path.join(controller_path, _linkdest), idxctx.logger)
                elif tb_res == 1:
                    idxctx.logger.warning("{}: index failures encountered on {}", idxctx.TS, tb)
                    with open(erred, "a") as fp:
                        print(tb, file=fp)
                    _rename_tb_link(tb, os.path.join(controller_path, "{}.1".format(_linkerrdest)), idxctx.logger)
                elif tb_res in (2, 3):
                    assert False, "Logic Bomb!  Unexpected tar ball handling result status {:d} for tar ball {}".format(tb_res, tb)
                    # echo "$TS: index configuration error $status on $result" >&4
                elif tb_res >= 4 or res <= 11:
                    # # Quietly skip these errors
                    with open(skipped, "a") as fp:
                        print(tb, file=fp)
                    _rename_tb_link(tb, os.path.join(controller_path, "{}.{:d}".format(_linkerrdest, tb_res)), idxctx.logger)
                else:
                    idxctx.logger.error("{}: index error {:d} encountered on {}", idxctx.TS, tb_res, tb)
                    with open(erred, "a") as fp:
                        print(tb, file=fp)
                    _rename_tb_link(tb, os.path.join(controller_path, _linkerrdest), idxctx.logger)
                idxctx.logger.info("Finished {} (size {:d})", tb, size)
        except Exception as e:
            idxctx.logger.exception("Unexpected setup error")
            res = 12
        else:
            # No exceptions while processing tar ball, success.
            res = 0
        finally:
            if idxctx:
                idxctx.dump_opctx()
            if options.debug_time_operations: _ts("Done", newline=True)

            idx = _count_lines(indexed)
            skp = _count_lines(skipped)
            err = _count_lines(erred)

            idxctx.logger.info("{}.{}: indexed {:d} (skipped {:d}) results, {:d} errors", _NAME_, idxctx.TS, idx, skp, err)

            if err > 0:
                if skp > 0:
                    subj = "{}.{} - Indexed {:d} results, skipped {:d} results, w/ {:d} errors".format(_NAME_, idxctx.TS, idx, skp, err)
                else:
                    subj = "{}.{} - Indexed {:d} results, w/ {:d} errors".format(_NAME_, idxctx.TS, idx, err)
            else:
                if skp > 0:
                    subj = "{}.{} - Indexed {:d} results, skipped {:d} results".format(_NAME_, idxctx.TS, idx, skp)
                else:
                    subj = "{}.{} - Indexed {:d} results".format(_NAME_, idxctx.TS, idx)

            report = os.path.join(tmpdir, "{}.{}.report".format(_NAME_, idxctx.TS))
            with open(report, "w") as fp:
                print(subj, file=fp)
                if idx > 0:
                    print("\nIndexed Results\n===============", file=fp)
                    with open(indexed) as ifp:
                        for line in ifp:
                            print(line, file=fp)
                if err > 0:
                    print("\nResults producing errors\n========================", file=fp)
                    with open(erred) as efp:
                        for line in efp:
                            print(line, file=fp)
                if skp > 0:
                    print("\nSkipped Results\n===============", file=fp)
                    with open(skipped) as sfp:
                        for line in sfp:
                            print(line, file=fp)
            report_status(idxctx.es, idxctx.logger, idxctx.config.LOGSDIR,
                    idxctx.idx_prefix, _NAME_, tstos(idxctx.time()), "status",
                    report)

    return res

###########################################################################
# Options handling
if __name__ == '__main__':
    parser = ArgumentParser(
        """Usage: {} [--config <path-to-config-file>] [--dump-index-patterns]"""
        """ [--time-ops] [--indexing-errors] [--dump_templates]""".format(_NAME_))
    parser.add_argument(
        "-C", "--config", dest="cfg_name",
        help="Specify config file")
    parser.set_defaults(cfg_name = os.environ.get("CONFIG"))
    parser.add_argument(
        "-E", "--indexing-errors", dest="indexing_errors",
        help="Name of a file to write JSON documents that fail to index")
    parser.add_argument(
        "-I", "--dump-index-patterns", action="store_true", dest="dump_index_patterns",
        help="Emit a list of index patterns used")
    parser.add_argument(
        "-Q", "--dump-templates", action="store_true", dest="dump_templates",
        help="Emit the full JSON document for each index template used")
    parser.add_argument(
        "-M", "--metadata", dest="metadata_string",
        help="Specify additional metadata (e.g. for browbeat) as a JSON document string")
    parser.add_argument(
        "-T", "--time-ops", action="store_true", dest="debug_time_operations",
        help="Time action making routines")
    parsed = parser.parse_args()
    status = main(parsed)
    sys.exit(status)
