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

import pbench
from pbench.indexer import PbenchTemplates, get_es, es_index, _op_type


class Existence(object):
    """Encapsulation of server-side reporting information for recording who,
    what, when, and how of a component's operation.
    """

    # We set the chunk size to 50 MB which is half the maximum payload size
    # that Elasticsearch typically handles.

    def __init__(self, config, name, controller, tbstatus, tarballts, es=None, hostname=None, version=None, templates=None):
        self.config = config
        self.name = name
        self.controller = controller
        self.tbstatus = tbstatus
        self.tarballts = tarballts
        self.logger = pbench.get_pbench_logger(name, config)

        # We always create a base "tracking" document composed of parameters
        # from the caller, and other environmental data. This document is used
        # as the foundation for the first document posted to the target
        # Elasticsearch instance with the `post_status()` method.  All
        # subsequent calls to the `post_status()` method will use that first
        # document ID as their parent document ID.  This allows us to have
        # multiple status updates associated with the initial Existence() caller.

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
        self.templates.update_templates(self.es, 'tarball-existence')

    @staticmethod
    def _make_json_payload(source):
        """Given a source dictionary, return its ID, and a formatted JSON
        payload.
        """
        the_bytes = json.dumps(source, sort_keys=True).encode('utf-8')
        source_id = hashlib.md5(the_bytes).hexdigest()
        return source, source_id, the_bytes.decode('utf-8')

    def _gen_no_json_payload(self, base_source):
        """Just yield the base source document since we do not have a text
        payload to add.
        """
        yield self._make_json_payload(base_source)

    def post_status(self, timestamp):
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
                "name": self.name,
                "controller": self.controller,
                "tbstatus": self.tbstatus,
                "tarballts": self.tarballts,
            }
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
                                "tarball-existence", source)
                        action = {
                            "_op_type": _op_type,
                            "_index": idx_name,
                            "_type": 'pbench-tarball-existence',
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
                        " retries: {:d})", pbench.tstos(end), end - beg,
                        successes, duplicates, failures, retries)
        except Exception:
            self.logger.exception("Failed to post status, name = {},"
                    " timestamp = {}",self.name, timestamp)
            raise
        return self.tracking_id
