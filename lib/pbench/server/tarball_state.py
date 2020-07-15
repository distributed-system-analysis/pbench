"""Reporting module for Tarballs.
"""

import sys
import os
import lzma
import json
import hashlib
import socket
from pathlib import Path
from configparser import Error as NoSectionError, NoOptionError

from pbench.common.logger import get_pbench_logger
from pbench.server import tstos
from pbench.server.indexer import PbenchTemplates, get_es, es_index, _op_type


class TarState:
    """Encapsulation of server-side reporting information for recording who,
    what, when, and how of a component's operation.
    """

    # We set the chunk size to 50 MB which is half the maximum payload size
    # that Elasticsearch typically handles.

    def __init__(
        self,
        config,
        name,
        es=None,
        pid=None,
        group_id=None,
        user_id=None,
        hostname=None,
        version=None,
        templates=None,
    ):

        self.config = config
        self.name = name
        self.listofdict = list()

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
        self.generated_by = dict(
            [
                ("commit_id", self.config.COMMIT_ID),
                ("group_id", _group_id),
                ("hostname", _hostname),
                ("pid", _pid),
                ("user_id", _user_id),
                ("version", version if version else ""),
            ]
        )
        # The "tracking_id" is the final MD5 hash of the first document
        # indexed via the `post_status()` method.
        self.tracking_id = None

        try:
            self.idx_prefix = config.get("Indexing", "index_prefix")
        except (NoOptionError, NoSectionError):
            # No index prefix so reporting will be performed via logging.
            self.idx_prefix = None
            self.es = None
        else:
            if es is None:
                try:
                    self.es = get_es(config, self.logger)
                except Exception:
                    self.logger.exception(
                        "Unexpected failure fetching" " Elasticsearch configuration"
                    )
                    # If we don't have an Elasticsearch configuration just use
                    # None to indicate logging should be used instead.
                    self.es = None
            else:
                self.es = es

        if templates is not None:
            self.templates = templates
        else:
            self.templates = PbenchTemplates(
                self.config.BINDIR, self.idx_prefix, self.logger
            )

        return

    def generateDict(self, tbname, controller):
        timestamp = tbname.rsplit("_", 1)[1][:-7]
        generateDict = {
            "name": tbname,
            "controller": controller,
            "script": self.name,
            "status": "FAILED",
            "creation_ts": timestamp,
        }

        source = {tbname: generateDict}
        self.listofdict.append(source)
        return

    def passedtb(self, tbname):
        self.listofdict[-1][tbname]["status"] = "PASSED"
        return

    @staticmethod
    def _make_json_payload(source):
        """Given a source dictionary, return its ID, and a formatted JSON
        payload.
        """
        the_bytes = json.dumps(source, sort_keys=True).encode("utf-8")
        source_id = hashlib.md5(the_bytes).hexdigest()
        return source, source_id, the_bytes.decode("utf-8")

    def _gen_no_json_payload(self, base_source):
        """Just yield the base source document since we do not have a text
        payload to add.
        """
        yield self._make_json_payload(base_source)

    def postreport(self, timestamp):

        try:
            if timestamp.startswith("run-"):
                timestamp = timestamp[4:]
            # Snip off the trailing "-<TZ>" - assumes that <TZ> does not
            # contain a "-"
            timestamp_noutc = timestamp.rsplit("-", 1)[0]

            base_source = {
                "@timestamp": timestamp_noutc,
                "@generated-by": self.generated_by,
                "tarball-status": self.listofdict,
                "doctype": "status",
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
                    fname = f"{self.name}.{timestamp}.xz"
                    fpath = Path(self.config.LOGSDIR, "tarball-status-report", fname)
                    with lzma.open(fpath, mode="w", preset=9) as fp:
                        fp.write(the_bytes)
                        for _, _, the_bytes in payload_gen:
                            fp.write(the_bytes)
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
                            "server-reports", source
                        )
                        action = {
                            "_op_type": _op_type,
                            "_index": idx_name,
                            "_type": "pbench-server-reports",
                            "_id": source_id,
                            "_source": source,
                        }
                        yield action

                es_res = es_index(
                    self.es, _es_payload_gen(payload_gen), sys.stderr, self.logger
                )

                beg, end, successes, duplicates, failures, retries = es_res
                if failures > 0:
                    log_action = self.logger.error
                elif duplicates > 0 or retries > 0:
                    log_action = self.logger.warning
                else:
                    assert (
                        successes >= 1
                        and duplicates == 0
                        and failures == 0
                        and retries == 0
                    ), "Logic Bomb!"
                    log_action = self.logger.debug
                log_action(
                    "posted status (start ts: {}, end ts: {}, duration: {:.2f}s,"
                    " successes: {:d}, duplicates: {:d}, failures: {:d},"
                    " retries: {:d})",
                    tstos(beg),
                    tstos(end),
                    end - beg,
                    successes,
                    duplicates,
                    failures,
                    retries,
                )
        except Exception:
            self.logger.exception(
                "Failed to post status, name = {},"
                " timestamp = {}, doctype = {}, file_to_index = {}",
                self.name,
                timestamp,
                "status",
            )
            raise

        return self.tracking_id
