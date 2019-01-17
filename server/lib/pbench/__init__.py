"""
Simple module level convenience functions.
"""

import sys, os, time, json, errno, logging, math, configtools, glob, shutil, \
    hashlib, re, copy, lzma

from datetime import datetime
from random import SystemRandom
from collections import Counter, deque
from configparser import ConfigParser, NoSectionError, NoOptionError
from urllib3 import Timeout, exceptions as ul_excs
try:
    from elasticsearch1 import VERSION as es_VERSION, Elasticsearch, helpers, exceptions as es_excs
except ImportError:
    from elasticsearch import VERSION as es_VERSION, Elasticsearch, helpers, exceptions as es_excs
try:
    from pbench.mock import MockElasticsearch
except ImportError:
    MockElasticsearch = None


def tstos(ts=None):
    return time.strftime("%Y-%m-%dT%H:%M:%S-%Z", time.gmtime(ts))

_do_ts = time.time
_r = SystemRandom()
_MAX_SLEEP_TIME = 120
_MAX_ERRMSG_LENGTH = 16384

def _calc_backoff_sleep(backoff):
    global _r
    b = math.pow(2, backoff)
    return _r.uniform(0, min(b, _MAX_SLEEP_TIME))


class _Message(object):
    """An object that stores a format string, expected to be using the
    "brace" style formatting, and the arguments object which will be used
    to satisfy the formats.

    This allows for a delay in the formatting of the final logging
    message string to a point when the log message will actually be
    emitted.

    Taken from the Python Logging Cookbook, https://docs.python.org/3.6/howto/logging-cookbook.html#use-of-alternative-formatting-styles.
    """
    def __init__(self, fmt, args):
        self.fmt = fmt
        self.args = args

    def __str__(self):
        return self.fmt.format(*self.args)


class _StyleAdapter(logging.LoggerAdapter):
    """Wrap a python logger object with a logging.LoggerAdapter that uses
    the _Message() object so that log messages will be formatted using
    "brace" style formatting.

    Taken from the Python Logging Cookbook, https://docs.python.org/3.6/howto/logging-cookbook.html#use-of-alternative-formatting-styles.
    """
    def __init__(self, logger, extra=None):
        super().__init__(logger, extra or {})

    def log(self, level, msg, *args, **kwargs):
        if self.isEnabledFor(level):
            msg, kwargs = self.process(msg, kwargs)
            self.logger._log(level, _Message(msg, args), (), **kwargs)


class _PbenchLogFormatter(logging.Formatter):
    """Custom logging.Formatter for pbench server processes / environments.

    The pbench log formatter provides ISO timestamps in the log messages,
    formatting using "brace" style string formats by default, removal of
    new line ASCII characters (replaced with "#012"), optional max line
    length handling (broken in half with an elipsis between the halves).

    This work was originally copied from:

        https://github.com/openstack/swift/blob/1d4249ee9d176d5563631521fb17aa24baf7fbf3/swift/common/utils.py

    The original license is Apache 2.0 (see below).  See the associated
    LICENSE.log_formatter, and AUTHORS.log_formatter files in the code
    base.
    ---
    Copyright (c) 2010-2012 OpenStack Foundation

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
    implied.

    See the License for the specific language governing permissions and
    limitations under the License.
    """

    def __init__(self, fmt=None, datefmt=None, style='{', max_line_length=0):
        super().__init__(fmt=fmt, datefmt=datefmt, style=style)
        self.max_line_length = max_line_length

    def format(self, record):
        # Included from Python's logging.Formatter and then altered slightly to
        # replace \n with #012
        record.message = record.getMessage()
        if self._fmt.find('{asctime}') >= 0:
            try:
                record.asctime = datetime.utcfromtimestamp(record.asctime).isoformat()
            except AttributeError:
                record.asctime = datetime.now().isoformat()
        msg = (self._fmt.format(**record.__dict__)).replace('\n', '#012')
        if record.exc_info:
            # Cache the traceback text to avoid converting it multiple times
            # (it's constant anyway)
            if not record.exc_text:
                record.exc_text = self.formatException(
                    record.exc_info).replace('\n', '#012')
        if record.exc_text:
            if not msg.endswith('#012'):
                msg = msg + '#012'
            msg = msg + record.exc_text
        if self.max_line_length > 0 and len(msg) > self.max_line_length:
            if self.max_line_length < 7:
                msg = msg[:self.max_line_length]
            else:
                approxhalf = (self.max_line_length - 5) // 2
                msg = msg[:approxhalf] + " ... " + msg[-approxhalf:]
        return msg

# Used to track the individual FileHandler's created by callers of
# get_pbench_logger().
_handlers = {}

def get_pbench_logger(caller, config):
    """Add a specific handler for the caller using the configured LOGSDIR.

    We also return a logger that supports "brace" style message formatting,
    e.g. logger.warning("that = {}", that)
    """
    pbench_logger = logging.getLogger(caller)
    if caller not in _handlers:
        pbench_logger.setLevel(logging.DEBUG)
        logdir = os.path.join(config.LOGSDIR, caller)
        try:
            os.mkdir(logdir)
        except FileExistsError:
            # directory already exists, ignore
            pass
        fh = logging.FileHandler(os.path.join(logdir, "{}.log".format(caller)))
        fh.setLevel(logging.DEBUG)
        try:
            environment = config.get('pbench-server', 'environment')
        except Exception as e:
            debug_unittest = False
        else:
            debug_unittest = (environment == 'unit-test')
        if not debug_unittest:
            logfmt = "{asctime} {levelname} {process} {thread} {name}.{module} {funcName} {lineno} -- {message}"
        else:
            logfmt = "1970-01-01T00:00:00.000000 {levelname} {name}.{module} {funcName} -- {message}"
        formatter = _PbenchLogFormatter(fmt=logfmt)
        fh.setFormatter(formatter)
        _handlers[caller] = fh
        pbench_logger.addHandler(fh)
    return _StyleAdapter(pbench_logger)


class BadConfig(Exception):
    pass


class PbenchConfig(object):
    """A simple class to wrap a ConfigParser object using the configtools
       style of multiple configuration files.
    """

    def __init__(self, cfg_name):
        # Enumerate the list of files
        config_files = configtools.file_list(cfg_name)
        config_files.reverse()

        self.conf = ConfigParser()
        self.files = self.conf.read(config_files)

        # Now fetch some default common pbench settings that are required.
        try:
            self.TOP = self.conf.get("pbench-server", "pbench-top-dir")
            if not os.path.isdir(self.TOP): raise BadConfig("Bad TOP={}".format(self.TOP))
            self.TMP = self.conf.get("pbench-server", "pbench-tmp-dir")
            if not os.path.isdir(self.TMP): raise BadConfig("Bad TMP={}".format(self.TMP))
            self.LOGSDIR = self.conf.get("pbench-server", "pbench-logs-dir")
            if not os.path.isdir(self.LOGSDIR): raise BadConfig("Bad LOGSDIR={}".format(self.LOGSDIR))
            self.BINDIR = self.conf.get("pbench-server", "script-dir")
            if not os.path.isdir(self.BINDIR): raise BadConfig("Bad BINDIR={}".format(self.BINDIR))
            self.LIBDIR = self.conf.get("pbench-server", "lib-dir")
            if not os.path.isdir(self.LIBDIR): raise BadConfig("Bad LIBDIR={}".format(self.LIBDIR))

            self.ARCHIVE = self.conf.get("pbench-server", "pbench-archive-dir")
            self.INCOMING = self.conf.get("pbench-server", "pbench-incoming-dir")
            # this is where the symlink forest is going to go
            self.RESULTS = self.conf.get("pbench-server", "pbench-results-dir")
            self.USERS = self.conf.get("pbench-server", "pbench-users-dir")
            # the scripts may use this to send status messages
            self.mail_recipients = self.conf.get("pbench-server", "mailto")
        except (NoOptionError, NoSectionError) as exc:
            raise BadConfig(str(exc))
        try:
            self.PBENCH_ENV = self.conf.get("pbench-server", "environment")
        except NoOptionError:
            self.PBENCH_ENV = ""

        # Constants

        # Force UTC everywhere
        self.TZ = "UTC"
        # Make all the state directories for the pipeline and any others
        # needed.  Every related state directories are paired together with
        # their final state at the end.
        self.LINKDIRS = "TODO BAD-MD5" \
                " TO-UNPACK UNPACKED MOVED-UNPACKED" \
                " TO-SYNC SYNCED" \
                " TO-LINK" \
                " TO-INDEX INDEXED WONT-INDEX" \
                " TO-COPY-SOS COPIED-SOS" \
                " TO-BACKUP" \
                " SATELLITE-MD5-PASSED SATELLITE-MD5-FAILED" \
                " TO-DELETE SATELLITE-DONE"
        # List of the state directories which will be excluded during rsync.
        # Note that range(1,12) generates the sequence [1..11] inclusively.
        self.EXCLUDE_DIRS = "_QUARANTINED " + self.LINKDIRS + " " + " ".join([ "WONT-INDEX.{:d}".format(i) for i in range(1,12) ])

    def get(self, *args, **kwargs):
        return self.conf.get(*args, **kwargs)


def _gen_json_payload(file_to_index, timestamp, name, doctype):
    with open(file_to_index, "r") as fp:
        text = fp.read()
    source = {
        "@timestamp": timestamp,
        "name": name,
        "doctype": doctype,
        "text": text
    }
    the_bytes = json.dumps(source, sort_keys=True).encode('utf-8')
    source_id = hashlib.md5(the_bytes).hexdigest()
    return source, source_id, the_bytes.decode('utf-8'), len(the_bytes)

def report_status(es, logger, LOGSDIR, idx_prefix, name, timestamp, doctype, file_to_index):
    try:
        if timestamp.startswith('run-'):
            timestamp = timestamp[4:]
        # Snip off the trailing "-<TZ>" - assumes that <TZ> does not contain a "-"
        timestamp_noutc = timestamp.rsplit('-', 1)[0]

        source, source_id, the_bytes, the_bytes_len = _gen_json_payload(
            file_to_index, timestamp_noutc, name, doctype)

        if es is None:
            # We don't have an Elasticsearch configuration, use syslog only.

            # Prepend the proper sequence to allow rsyslog to recognize JSON and
            # process it
            payload = "@cee:{}".format(the_bytes)
            if len(payload) > 4096:
                # Compress the full message to a file.
                # xz -9 -c ${tmp}/payload > $LOGSDIR/$name/${prog}-payload.${timestamp%-*}.xz
                fname = "report-status-payload.{}.xz".format(timestamp_noutc)
                fpath = os.path.join(LOGSDIR, name, fname)
                with lzma.open(fpath, mode="w", preset=9) as fp:
                    f.write(payload)
            # Always log the first 4,096 bytes
            logger.info("{}", payload[:4096])
        else:
            # We have an Elasticsearch configuration.

            # Snip off the time part of the timestamp to get YYYY-MM for the
            # index name.
            datestamp = timestamp_noutc.rsplit('-', 1)[0]

            idx_name = "{}-server-reports.{}".format(idx_prefix, datestamp)
            action = {
                "_op_type": _op_type,
                "_index": idx_name,
                "_type": 'pbench-server-reports',
                "_id": source_id,
                "_source": source
                }
            es_res = es_index(es, [ action ], sys.stderr, logger)
            beg, end, successes, duplicates, failures, retries = es_res
            do_log = logger.info if successes == 1 else logger.warning
            do_log("posted status (end ts: {}, duration: {:.2f}s,"
                    " successes: {:d}, duplicates: {:d}, failures: {:d},"
                    " retries: {:d})", tstos(end), end - beg, successes,
                    duplicates, failures, retries)
    except Exception:
        logger.exception("Failed to post status, name = {}, timestamp = {},"
                " doctype = {}, file_to_index = {}", name, timestamp, doctype,
                file_to_index)
    return 0

def quarantine(dest, logger, *files):
    """Quarantine problematic tarballs.
    Errors here are fatal but we log an error message to help diagnose
    problems.
    """
    try:
        os.mkdir(dest)
    except FileExistsError:
        # directory already exists, ignore
        pass
    except Exception:
        logger.exception("quarantine {} {!r}: \"mkdir -p {}/\" failed", dest, files, dest)
        sys.exit(101)

    for afile in files:
        if not os.path.exists(afile) and not os.path.islink(afile):
            continue
        try:
            shutil.move(afile, os.path.join(dest, os.path.basename(afile)))
        except Exception:
            logger.exception("quarantine {} {!r}: \"mv {} {}/\" failed", dest, files, afile, dest)
            sys.exit(102)

def _get_es_hosts(config, logger):
    """
    Return list of dicts (a single dict for now) -
    that's what ES is expecting.
    """
    try:
        URL = config.get('Indexing', 'server')
    except NoSectionError:
        logger.error("Need an [Indexing] section with host and port defined"
                " in {} configuration file", " ".join(config.__files__))
        return None
    except NoOptionError:
        host = config.get('Indexing', 'host')
        port = config.get('Indexing', 'port')
    else:
        host, port = URL.rsplit(':', 1)
    timeoutobj = Timeout(total=1200, connect=10, read=_read_timeout)
    return [dict(host=host, port=port, timeout=timeoutobj),]

def get_es(config, logger):
    try:
        debug_unittest = config.get('Indexing', 'debug_unittest')
    except Exception as e:
        debug_unittest = False
    else:
        debug_unittest = bool(debug_unittest)
    hosts = _get_es_hosts(config, logger)
    if debug_unittest:
        if MockElasticsearch is None:
            raise Exception("MockElasticsearch is not available!")
        es = MockElasticsearch(hosts, max_retries=0)
        global helpers
        helpers.streaming_bulk = es.mockstrm.streaming_bulk
        def _ts():
            return 0
        global _do_ts
        _do_ts = _ts
    else:
        # FIXME: we should just change these two loggers to write to a
        # file instead of setting the logging level up so high.
        logging.getLogger("urllib3").setLevel(logging.FATAL)
        logging.getLogger("elasticsearch1").setLevel(logging.FATAL)
        es = Elasticsearch(hosts, max_retries=0)
    return es


class JsonFileError(Exception):
    pass


class MappingFileError(JsonFileError):
    pass


class TemplateError(Exception):
    pass


class PbenchTemplates(object):
    """Encapsulation of methods for loading / working with all the Pbench
    templates for Elasticsearch.
    """
    @staticmethod
    def _load_json(json_fn):
        """Simple wrapper function to load a JSON object from the given file,
        raising the JsonFileError when bad JSON data is encountered.
        """
        with open(json_fn, "r") as jsonfp:
            try:
                data = json.load(jsonfp)
            except ValueError as err:
                raise JsonFileError("{}: {}".format(json_fn, err))
        return data

    @staticmethod
    def _fetch_mapping(mapping_fn):
        """Fetch the mapping JSON data from the given file.

        Returns a tuple consisting of the mapping name pulled from the file, and
        the python dictionary loaded from the JSON file.

        Raises MappingFileError if it encounters any problem loading the file.
        """
        mapping = PbenchTemplates._load_json(mapping_fn)
        keys = list(mapping.keys())
        if len(keys) != 1:
            raise MappingFileError(
                "Invalid mapping file: {}".format(mapping_fn))
        return keys[0], mapping[keys[0]]

    def __init__(self, basepath, idx_prefix, logger, \
                known_tool_handlers=None, _dbg=0):
        # Where to find the mappings
        MAPPING_DIR = os.path.join(
            os.path.dirname(basepath), 'lib', 'mappings')
        # Where to find the settings
        SETTING_DIR = os.path.join(
            os.path.dirname(basepath), 'lib', 'settings')

        self.versions = {}
        self.templates = {}
        self.idx_prefix = idx_prefix
        self.logger = logger
        self.known_tool_handlers = known_tool_handlers
        self._dbg = _dbg

        # Pbench report status mapping and settings.
        server_reports_mappings = {}
        mfile = os.path.join(MAPPING_DIR, "server-reports.json")
        key, mapping = self._fetch_mapping(mfile)
        try:
            idxver = mapping['_meta']['version']
        except KeyError:
            raise MappingFileError(
                "{} mapping missing _meta field in {}".format(key, mfile))
        if self._dbg > 5:
            print("fetch_mapping: {} -- {}\n{}\n".format(mfile, key,
                    json.dumps(mapping, indent=4, sort_keys=True)))
        server_reports_mappings[key] = mapping
        server_reports_settings = self._load_json(
            os.path.join(SETTING_DIR, "server-reports.json"))

        ip = self.index_patterns['server-reports']
        idxname = ip['idxname']
        server_reports_template_name = ip['template_name'].format(
            prefix=self.idx_prefix, version=idxver, idxname=idxname)
        server_reports_template_body = dict(
            template=ip['template_pat'].format(prefix=self.idx_prefix,
                version=idxver, idxname=idxname),
            settings=server_reports_settings,
            mappings=server_reports_mappings)
        self.templates[server_reports_template_name] = server_reports_template_body
        self.versions['server-reports'] = idxver

        # For v1 Elasticsearch, we need to use two doc types to have
        # parent/child relationship between run documents and
        # table-of-contents documents. So we load two mappings in a loop, but
        # only one settings file below.
        run_mappings = {}
        idxver = None
        for mapping_fn in glob.iglob(os.path.join(MAPPING_DIR, "run*.json")):
            key, mapping = self._fetch_mapping(mapping_fn)
            try:
                idxver_val = mapping['_meta']['version']
            except KeyError:
                raise MappingFileError(
                    "{} mapping missing _meta field in {}".format(
                        key, mapping_fn))
            else:
                if idxver is None:
                    idxver = idxver_val
                else:
                    if idxver != idxver_val:
                        raise MappingFileError("{} mappings have mismatched"
                            " version fields in {}".format(key, mapping_fn))
            if self._dbg > 5:
                print("fetch_mapping: {} -- {}\n{}\n".format(mapping_fn, key,
                        json.dumps(mapping, indent=4, sort_keys=True)))
            run_mappings[key] = mapping
        run_settings = self._load_json(os.path.join(SETTING_DIR, "run.json"))

        ip = self.index_patterns['run-data']
        idxname = ip['idxname']
        # The API body for the template create() contains a dictionary with the
        # settings and the mappings.
        run_template_name = ip['template_name'].format(prefix=self.idx_prefix,
            version=idxver, idxname=idxname)
        run_template_body = dict(
            template=ip['template_pat'].format(prefix=self.idx_prefix,
                version=idxver, idxname=idxname),
            settings=run_settings,
            mappings=run_mappings)
        self.templates[run_template_name] = run_template_body
        # Remember the version we pulled from the mapping file, record it in
        # both the run and toc-entry names.  NOTE: this use of two mappings
        # will go away with V6 Elasticsearch.
        self.versions['run-data'] = idxver
        self.versions['toc-data'] = idxver

        # Next we load all the result-data mappings and settings.
        result_mappings = {}
        mfile = os.path.join(MAPPING_DIR, "result-data.json")
        key, mapping = self._fetch_mapping(mfile)
        try:
            idxver = mapping['_meta']['version']
        except KeyError:
            raise MappingFileError(
                "{} mapping missing _meta field in {}".format(key, mfile))
        if self._dbg > 5:
            print("fetch_mapping: {} -- {}\n{}\n".format(mfile, key,
                    json.dumps(mapping, indent=4, sort_keys=True)))
        result_mappings[key] = mapping
        mfile = os.path.join(MAPPING_DIR, "result-data-sample.json")
        key, mapping = self._fetch_mapping(mfile)
        try:
            idxver = mapping['_meta']['version']
        except KeyError:
            raise MappingFileError(
                "{} mapping missing _meta field in {}".format(key, mfile))
        if self._dbg > 5:
            print("fetch_mapping: {} -- {}\n{}\n".format(mfile, key,
                    json.dumps(mapping, indent=4, sort_keys=True)))
        result_mappings[key] = mapping
        result_settings = self._load_json(os.path.join(SETTING_DIR, "result-data.json"))

        ip = self.index_patterns['result-data']
        idxname = ip['idxname']
        result_template_name = ip['template_name'].format(prefix=self.idx_prefix,
                version=idxver, idxname=idxname)
        result_template_body = dict(
            template=ip['template_pat'].format(prefix=self.idx_prefix,
                version=idxver, idxname=idxname),
            settings=result_settings,
            mappings=result_mappings)
        self.templates[result_template_name] = result_template_body
        self.versions['result-data'] = idxver

        # Now for the tool data mappings. First we fetch the base skeleton they
        # all share.
        skel = self._load_json(os.path.join(MAPPING_DIR, "tool-data-skel.json"))
        ip = self.index_patterns['tool-data']

        # Next we load all the tool fragments
        fpat = re.compile(r'tool-data-frag-(?P<toolname>.+)\.json')
        tool_mapping_frags = {}
        for mapping_fn in glob.iglob(os.path.join(MAPPING_DIR, "tool-data-frag-*.json")):
            m = fpat.match(os.path.basename(mapping_fn))
            toolname = m.group('toolname')
            if self.known_tool_handlers is not None:
                if toolname not in self.known_tool_handlers:
                    MappingFileError("Unsupported tool '{}' mapping file {}".format(
                        toolname, mapping_fn))
            mapping = self._load_json(mapping_fn)
            try:
                idxver = mapping['_meta']['version']
            except KeyError:
                raise MappingFileError(
                    "{} mapping missing _meta field in {}".format(key, mapping_fn))
            if self._dbg > 5:
                print("fetch_mapping: {} -- {}\n{}\n".format(mapping_fn, toolname,
                        json.dumps(mapping, indent=4, sort_keys=True)))
            del mapping['_meta']
            tool_mapping_frags[toolname] = mapping
            self.versions[ip['idxname'].format(tool=toolname)] = idxver
        tool_settings = self._load_json(os.path.join(SETTING_DIR, "tool-data.json"))

        tool_templates = []
        for toolname,frag in tool_mapping_frags.items():
            tool_skel = copy.deepcopy(skel)
            idxname = ip['idxname'].format(tool=toolname)
            tool_skel['_meta'] = dict(version=self.versions[idxname])
            tool_skel['properties'][toolname] = frag
            tool_mapping = dict([("pbench-{}".format(idxname), tool_skel)])
            tool_template_name = ip['template_name'].format(prefix=self.idx_prefix,
                version=idxver, idxname=idxname)
            tool_template_body = dict(
                template=ip['template_pat'].format(prefix=self.idx_prefix,
                    version=self.versions[idxname], idxname=idxname),
                settings=tool_settings,
                mappings=tool_mapping)
            self.templates[tool_template_name] = tool_template_body

    index_patterns = {
        'result-data': {
            'idxname':       "result-data",
            'template_name': "{prefix}.v{version}.{idxname}",
            'template_pat':  "{prefix}.v{version}.{idxname}.*",
            'template':      "{prefix}.v{version}.{idxname}.{year}-{month}-{day}",
            'desc':          "Daily result data (any data generated by the"
                    " benchmark) for all pbench result tar balls;"
                    " e.g prefix.v0.result-data.YYYY-MM-DD"
        },
        'run-data': {
            'idxname':       "run",
            'template_name': "{prefix}.v{version}.{idxname}",
            'template_pat':  "{prefix}.v{version}.{idxname}.*",
            'template':      "{prefix}.v{version}.{idxname}.{year}-{month}",
            'desc':          "Monthly pbench run metadata for index tar balls;"
                    " contains directories, file names, and their size,"
                    " permissions, etc.; e.g. prefix.v0.run.YYYY-MM"
        },
        'server-reports': {
            'idxname':       "server-reports",
            'template_name': "{prefix}.v{version}.{idxname}",
            'template_pat':  "{prefix}.v{version}.{idxname}.*",
            'template':      "{prefix}.v{version}.{idxname}.{year}-{month}",
            'desc':          "Monthly pbench server status reports for all"
                    " cron jobs; e.g. prefix.v0.server-reports.YYYY-MM"
        },
        'toc-data': {
            'idxname':       "run",
            'template_name': "{prefix}.v{version}.{idxname}",
            'template_pat':  "{prefix}.v{version}.{idxname}.*",
            'template':      "{prefix}.v{version}.{idxname}.{year}-{month}",
            'desc':          "Monthly table of contents metadata for index tar"
                    " balls; contains directories, file names, and their size,"
                    " permissions, etc.; e.g. prefix.v0.run.YYYY-MM"
        },
        'tool-data': {
            'idxname':       "tool-data-{tool}",
            'template_name': "{prefix}.v{version}.{idxname}",
            'template_pat':  "{prefix}.v{version}.{idxname}.*",
            'template':      "{prefix}.v{version}.{idxname}.{year}-{month}-{day}",
            'desc':          "Daily tool data for all tools land in indices"
                    " named by tool; e.g. prefix.v0.tool-data-iostat.YYYY-MM-DD"
        }
    }

    def dump_idx_patterns(self):
        patterns = self.index_patterns
        pattern_names = [idx for idx in patterns]
        pattern_names.sort()
        for idx in pattern_names:
            if idx != "tool-data":
                idxname = patterns[idx]['idxname']
                print(patterns[idx]['template'].format(prefix=self.idx_prefix,
                        version=self.versions[idx], idxname=idxname,
                        year="YYYY", month="MM", day="DD"))
                print(patterns[idx]['desc'], '\n')
            else:
                tool_names = [tool for tool in self.known_tool_handlers \
                        if self.known_tool_handlers[tool] is not None]
                tool_names.sort()
                for tool_name in tool_names:
                    idxname = patterns[idx]['idxname'].format(tool=tool_name)
                    print(patterns[idx]['template'].format(
                            prefix=self.idx_prefix,
                            version=self.versions[idxname], idxname=idxname,
                            year="YYYY", month="MM", day="DD"))
                print(patterns[idx]['desc'], '\n')
        sys.stdout.flush()

    def dump_templates(self):
        template_names = [name for name in self.templates]
        template_names.sort()
        for name in template_names:
            print("\n\nTemplate: {}\n\n{}\n".format(name,
                    json.dumps(self.templates[name], indent=4, sort_keys=True)))
        sys.stdout.flush()

    def update_templates(self, es, target_name=None):
        """Push the various Elasticsearch index templates required by pbench.
        """
        if target_name is not None:
            idxname = self.index_patterns[target_name]['idxname']
        else:
            idxname = None
        template_names = [name for name in self.templates]
        template_names.sort()
        successes = retries = 0
        beg = end = None
        for name in template_names:
            if idxname is not None and not name.endswith(idxname):
                # If we were asked to only load a given template name, skip
                # all non-matching templates.
                continue
            try:
                _beg, _end, _retries = es_put_template(es,
                        name=name, body=self.templates[name])
            except Exception as e:
                raise TemplateError(e)
            else:
                successes += 1
                if beg is None:
                    beg = _beg
                end = _end
                retries += _retries
        self.logger.info("done templates (end ts: {}, duration: {:.2f}s,"
                " successes: {:d}, retries: {:d})",
                tstos(end), end - beg, successes, retries)


def es_put_template(es, name=None, body=None):
    assert name is not None and body is not None
    retry = True
    retry_count = 0
    backoff = 1
    beg, end = _do_ts(), None
    # Derive the mapping name from the template name
    mapping_name = "pbench-{}".format(name.split('.')[2])
    try:
        body_ver = int(body['mappings'][mapping_name]['_meta']['version'])
    except KeyError as e:
        raise Exception("Bad template, {}, could not derive mapping name, {}: {!r}".format(name, mapping_name, e))
    while retry:
        try:
            tmpl = es.indices.get_template(name=name)
        except es_excs.TransportError as exc:
            # Only retry on certain 500 errors
            if exc.status_code != 404:
                if exc.status_code not in [500, 503, 504]:
                    raise
                time.sleep(_calc_backoff_sleep(backoff))
                backoff += 1
                retry_count += 1
                continue
        except es_excs.ConnectionError as exc:
            # We retry all connection errors
            time.sleep(_calc_backoff_sleep(backoff))
            backoff += 1
            retry_count += 1
            continue
        else:
            try:
                tmpl_ver = int(tmpl[name]['mappings'][mapping_name]['_meta']['version'])
            except KeyError as e:
                pass
            else:
                if tmpl_ver == body_ver:
                    break
        try:
            es.indices.put_template(name=name, body=body)
        except es_excs.TransportError as exc:
            # Only retry on certain 500 errors
            if exc.status_code not in [500, 503, 504]:
                raise
            time.sleep(_calc_backoff_sleep(backoff))
            backoff += 1
            retry_count += 1
        except es_excs.ConnectionError as exc:
            # We retry all connection errors
            time.sleep(_calc_backoff_sleep(backoff))
            backoff += 1
            retry_count += 1
        else:
            retry = False
    end = _do_ts()
    return beg, end, retry_count


# Always use "create" operations, as we also ensure each JSON document being
# indexed has an "_id" field, so we can tell when we are indexing duplicate
# data.
_op_type = "create"
# 100,000 minute timeouts talking to Elasticsearch; basically we just don't
# want to timeout waiting for Elasticsearch and then have to retry, as that
# can add undue burden to the Elasticsearch cluster.
_read_timeout = 100000*60.0
_request_timeout = 100000*60.0

def es_index(es, actions, errorsfp, logger, _dbg=0):
    """
    Now do the indexing specified by the actions.
    """
    # These need to be defined before the closure below. These work because
    # a closure remembers the binding of a name to an object. If integer
    # objects were used, the name would be bound to that integer value only
    # so for the retries, incrementing the integer would change the outer
    # scope's view of the name.  By using a Counter object, the name to
    # object binding is maintained, but the object contents are changed.
    actions_deque = deque()
    actions_retry_deque = deque()
    retries_tracker = Counter()

    def actions_tracking_closure(cl_actions):
        for cl_action in cl_actions:
            for field in ('_id', '_index', '_type'):
                assert field in cl_action, "Action missing '{}' field:" \
                        " {!r}".format(field, cl_action)
            assert _op_type == cl_action['_op_type'], "Unexpected _op_type" \
                    " value '{}' in action {!r}".format(
                    cl_action['_op_type'], cl_action)

            actions_deque.append((0, cl_action))   # Append to the right side ...
            yield cl_action
            # if after yielding an action some actions appear on the retry deque
            # start yielding those actions until we drain the retry queue.
            backoff = 1
            while len(actions_retry_deque) > 0:
                time.sleep(_calc_backoff_sleep(backoff))
                retries_tracker['retries'] += 1
                retry_actions = []
                # First drain the retry deque entirely so that we know when we
                # have cycled through the entire list to be retried.
                while len(actions_retry_deque) > 0:
                    retry_actions.append(actions_retry_deque.popleft())
                for retry_count, retry_action in retry_actions:
                    # Append to the right side ...
                    actions_deque.append((retry_count, retry_action))
                    yield retry_action
                # if after yielding all the actions to be retried, some show up
                # on the retry deque again, we extend our sleep backoff to avoid
                # pounding on the ES instance.
                backoff += 1

    beg, end = _do_ts(), None
    successes = 0
    duplicates = 0
    failures = 0

    # Create the generator that closes over the external generator, "actions"
    generator = actions_tracking_closure(actions)

    streaming_bulk_generator = helpers.streaming_bulk(
            es, generator, raise_on_error=False,
            raise_on_exception=False, request_timeout=_request_timeout)

    for ok, resp_payload in streaming_bulk_generator:
        retry_count, action = actions_deque.popleft()
        try:
            resp = resp_payload[_op_type]
        except KeyError as e:
            assert not ok, "{!r}".format(ok)
            assert e.args[0] == _op_type, "e.args = {!r}, _op_type = {!r}".format(e.args, _op_type)
            # For whatever reason, some errors are always returned using
            # the "index" operation type instead of _op_type (e.g. "create"
            # op type still comes back as an "index" response).
            try:
                resp = resp_payload['index']
            except KeyError:
                # resp is not of expected form; set it to the complete
                # payload, so that it can be reported properly below.
                resp = resp_payload
        try:
            status = resp['status']
        except KeyError as e:
            assert not ok
            # Limit the length of the error message.
            logger.error("{!r}", e)
            status = 999
        else:
            assert action['_id'] == resp['_id']
        if ok:
            successes += 1
        else:
            if status == 409:
                if retry_count == 0:
                    # Only count duplicates if the retry count is 0 ...
                    duplicates += 1
                else:
                    # ... otherwise consider it successful.
                    successes += 1
            elif status == 400:
                try:
                    exc_payload = resp['exception']
                except KeyError:
                    pass
                else:
                    resp['exception'] = repr(exc_payload)
                jsonstr = json.dumps({ "action": action, "ok": ok, "resp": resp, "retry_count": retry_count, "timestamp": tstos(_do_ts()) }, indent=4, sort_keys=True)
                print(jsonstr, file=errorsfp)
                errorsfp.flush()
                failures += 1
            else:
                try:
                    exc_payload = resp['exception']
                except KeyError:
                    pass
                else:
                    resp['exception'] = repr(exc_payload)
                try:
                    error = resp['error']
                except KeyError:
                    error = ""
                if status == 403 and error.startswith("IndexClosedException"):
                    # Don't retry closed index exceptions
                    jsonstr = json.dumps({ "action": action, "ok": ok, "resp": resp, "retry_count": retry_count, "timestamp": tstos(_do_ts()) }, indent=4, sort_keys=True)
                    print(jsonstr, file=errorsfp)
                    errorsfp.flush()
                    failures += 1
                else:
                    # Retry all other errors.
                    # Limit the length of the error message.
                    logger.warning("retrying action: {}", json.dumps(resp)[:_MAX_ERRMSG_LENGTH])
                    actions_retry_deque.append((retry_count + 1, action))

    end = _do_ts()

    assert len(actions_deque) == 0
    assert len(actions_retry_deque) == 0

    return (beg, end, successes, duplicates, failures, retries_tracker['retries'])
