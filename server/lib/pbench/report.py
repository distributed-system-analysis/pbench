"""Reporting module for pbench server.
"""

import sys
import os
import lzma
import math
import json
import hashlib
import socket
from configparser import Error as NoSectionError, NoOptionError

from pbench import tstos, get_pbench_logger
from pbench.indexer import PbenchTemplates, get_es, es_index, _op_type


class Report(object):
    """Encapsulation of server-side reporting information for recording who,
    what, when, and how of a component's operation.
    """

    # We set the chunk size to 50 MB which is half the maximum payload size
    # that Elasticsearch typically handles.
    _CHUNK_SIZE = 50 * 1024 * 1024

    def __init__(self, config, name, es=None, pid=None, group_id=None,
                user_id=None, hostname=None, version=None, templates=None):
        self.config = config
        self.name = name
        self.logger = get_pbench_logger(name, config)

        # We always create a base "tracking" document composed of parameters
        # from the caller, and other environmental data. This document is used
        # as the foundation for the first document posted to the target
        # Elasticsearch instance with the `post_status()` method.  All
        # subsequent calls to the `post_status()` method will use that first
        # document ID as their parent document ID.  This allows us to have
        # multiple status updates associated with the initial Report() caller.
        if config._unittests:
            _hostname = "example.com"
            _pid = 42
            _group_id = 43
            _user_id = 44
        else:
            _hostname = hostname if hostname else socket.gethostname()
            _pid = pid if pid else os.getpid()
            _group_id = group_id if group_id else os.getgid()
            _user_id = user_id if user_id else os.getuid()
        self.generated_by = dict([
            ('commit_id', self.config.COMMIT_ID),
            ('group_id', _group_id),
            ('hostname', _hostname),
            ('pid', _pid),
            ('user_id', _user_id),
            ('version', version if version else '')
        ])
        # The "tracking_id" is the final MD5 hash of the first document
        # indexed via the `post_status()` method.
        self.tracking_id = None
        try:
            self.idx_prefix = config.get('Indexing', 'index_prefix')
        except (NoOptionError, NoSectionError):
            # No index prefix so reporting will be performed via logging.
            self.idx_prefix = None
            self.es = None
        else:
            if es is None:
                try:
                    self.es = get_es(config, self.logger)
                except Exception:
                    self.logger.exception("Unexpected failure fetching"
                            " Elasticsearch configuration")
                    # If we don't have an Elasticsearch configuration just use
                    # None to indicate logging should be used instead.
                    self.es = None
            else:
                self.es = es
        if templates is not None:
            self.templates = templates
        else:
            self.templates = PbenchTemplates(self.config.BINDIR,
                    self.idx_prefix, self.logger)

    def init_report_template(self):
        """Setup the Elasticsearch templates needed for properly indexing
        report documents. This is only needed by non-'pbench-index' use cases.
        """
        if self.es is None:
            return
        self.templates.update_templates(self.es, 'server-reports')

    @staticmethod
    def _make_json_payload(source):
        """Given a source dictionary, return its ID, and a formatted JSON
        payload.
        """
        the_bytes = json.dumps(source, sort_keys=True).encode('utf-8')
        source_id = hashlib.md5(the_bytes).hexdigest()
        return source, source_id, the_bytes.decode('utf-8')

    def _gen_json_payload(self, base_source, file_to_index):
        """Generate a series of JSON documents to be indexed, where the text
        payload has a maximum size of 50 MB.
        """
        total_size = os.path.getsize(file_to_index)
        number_of_chunks = int(math.ceil(total_size / self._CHUNK_SIZE))
        chunk_id = 0
        with open(file_to_index, "r") as fp:
            EOF = False
            while not EOF:
                chunk_id += 1
                text = fp.read(self._CHUNK_SIZE)
                if not text:
                    EOF = True
                else:
                    source = {
                        "chunk_id": chunk_id,
                        "total_chunks": number_of_chunks,
                        "total_size": total_size,
                        "text": text
                    }
                    source.update(base_source)
                    yield self._make_json_payload(source)

    def _gen_no_json_payload(self, base_source):
        """Just yield the base source document since we do not have a text
        payload to add.
        """
        yield self._make_json_payload(base_source)

    def post_status(self, timestamp, doctype, file_to_index=None):
        """Post a status record, with an optional file payload to index along
        with the base tracking document.

        We return the tracking ID use for this report object.
        """
        try:
            if timestamp.startswith('run-'):
                timestamp = timestamp[4:]
            # Snip off the trailing "-<TZ>" - assumes that <TZ> does not
            # contain a "-"
            timestamp_noutc = timestamp.rsplit('-', 1)[0]

            base_source = {
                "@timestamp": timestamp_noutc,
                "@generated-by": self.generated_by,
                "name": self.name,
                "doctype": doctype
            }
            if file_to_index:
                payload_gen = self._gen_json_payload(base_source,
                        file_to_index)
            else:
                payload_gen = self._gen_no_json_payload(base_source)

            if self.es is None:
                # We don't have an Elasticsearch configuration, use syslog
                # only.

                # Prepend the proper sequence to allow rsyslog to recognize
                # JSON and process it. We only use the first chunk generated.
                _, self.tracking_id, the_bytes = next(payload_gen)
                payload = "@cee:{}".format(the_bytes)
                if len(payload) > 4096:
                    # Compress the full message to a file.
                    fname = "report-status-payload.{}.{}.xz".format(self.name,
                            timestamp_noutc)
                    fpath = os.path.join(self.config.LOGSDIR, self.name, fname)
                    with lzma.open(fpath, mode="w", preset=9) as fp:
                        f.write(the_bytes)
                        for _, _, the_bytes in payload_gen:
                            f.write(the_bytes)
                # Always log the first 4,096 bytes
                self.logger.info("{}", payload[:4096])
            else:
                # We have an Elasticsearch configuration.

                def _es_payload_gen(_payload_gen):
                    for source, source_id, _ in _payload_gen:
                        if self.tracking_id is None:
                            # First generated document becomes the tracking ID.
                            self.tracking_id = source_id
                        idx_name = self.templates.generate_index_name(
                                "server-reports", source)
                        action = {
                            "_op_type": _op_type,
                            "_index": idx_name,
                            "_type": 'pbench-server-reports',
                            "_id": source_id,
                            "_source": source
                        }
                        yield action
                es_res = es_index(self.es, _es_payload_gen(payload_gen),
                        sys.stderr, self.logger)
                beg, end, successes, duplicates, failures, retries = es_res
                do_log = self.logger.info if successes == 1 \
                        else self.logger.warning
                do_log("posted status (end ts: {}, duration: {:.2f}s,"
                        " successes: {:d}, duplicates: {:d}, failures: {:d},"
                        " retries: {:d})", tstos(end), end - beg, successes,
                        duplicates, failures, retries)
        except Exception:
            self.logger.exception("Failed to post status, name = {},"
                    " timestamp = {}, doctype = {}, file_to_index = {}", self.name,
                    timestamp, doctype, file_to_index)
            raise
        return self.tracking_id
