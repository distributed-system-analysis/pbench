import copy
import glob
import json
import os
import pyesbulk
import re
import sys

from collections import Counter
from pathlib import Path

from pbench.common.exceptions import (
    BadDate,
    MappingFileError,
    JsonFileError,
    TemplateError,
)
from pbench.server import tstos


class PbenchTemplates:
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
        key = Path(mapping_fn).stem
        mapping = PbenchTemplates._load_json(mapping_fn)
        try:
            idxver = mapping["_meta"]["version"]
        except KeyError:
            raise MappingFileError(
                "{} mapping missing _meta field in {}".format(key, mapping_fn)
            )
        return key, idxver, mapping

    _fpat = re.compile(r"tool-data-frag-(?P<toolname>.+)\.json")

    def __init__(self, basepath, idx_prefix, logger, known_tool_handlers=None, _dbg=0):
        # Where to find the mappings
        MAPPING_DIR = os.path.join(os.path.dirname(basepath), "lib", "mappings")
        # Where to find the settings
        SETTING_DIR = os.path.join(os.path.dirname(basepath), "lib", "settings")

        self.versions = {}
        self.templates = {}
        self.idx_prefix = idx_prefix
        self.logger = logger
        self.known_tool_handlers = known_tool_handlers
        self._dbg = _dbg

        # Pbench report status mapping and settings.
        mfile = os.path.join(MAPPING_DIR, "server-reports.json")
        key, idxver, mapping = self._fetch_mapping(mfile)
        server_reports_settings = self._load_json(
            os.path.join(SETTING_DIR, "server-reports.json")
        )

        ip = self.index_patterns[key]
        idxname = ip["idxname"]
        server_reports_template_name = ip["template_name"].format(
            prefix=self.idx_prefix, version=idxver, idxname=idxname
        )
        server_reports_template_body = dict(
            index_patterns=ip["template_pat"].format(
                prefix=self.idx_prefix, version=idxver, idxname=idxname
            ),
            settings=server_reports_settings,
            mappings=mapping,
        )
        self.templates[server_reports_template_name] = server_reports_template_body
        self.versions["server-reports"] = idxver

        run_settings = self._load_json(os.path.join(SETTING_DIR, "run.json"))
        for mapping_fn in glob.iglob(os.path.join(MAPPING_DIR, "run*.json")):
            key, idxver, mapping = self._fetch_mapping(mapping_fn)
            ip = self.index_patterns[key]
            idxname = ip["idxname"]
            # The API body for the template create() contains a dictionary with the
            # settings and the mappings.
            run_template_name = ip["template_name"].format(
                prefix=self.idx_prefix, version=idxver, idxname=idxname
            )
            run_template_body = dict(
                index_patterns=ip["template_pat"].format(
                    prefix=self.idx_prefix, version=idxver, idxname=idxname
                ),
                settings=run_settings,
                mappings=mapping,
            )
            self.templates[run_template_name] = run_template_body
            self.versions[key] = idxver

        # Next we load the result-data mappings and settings.
        result_settings = self._load_json(os.path.join(SETTING_DIR, "result-data.json"))
        for mapping_fn in glob.iglob(os.path.join(MAPPING_DIR, "result-data*.json")):
            mfile = os.path.join(MAPPING_DIR, mapping_fn)
            key, idxver, mapping = self._fetch_mapping(mfile)
            ip = self.index_patterns[key]
            idxname = ip["idxname"]
            result_template_name = ip["template_name"].format(
                prefix=self.idx_prefix, version=idxver, idxname=idxname
            )
            result_template_body = dict(
                index_patterns=ip["template_pat"].format(
                    prefix=self.idx_prefix, version=idxver, idxname=idxname
                ),
                settings=result_settings,
                mappings=mapping,
            )
            self.templates[result_template_name] = result_template_body
            self.versions[key] = idxver

        # Now for the tool data mappings. First we fetch the base skeleton they
        # all share.
        skel = self._load_json(os.path.join(MAPPING_DIR, "tool-data-skel.json"))
        ip = self.index_patterns["tool-data"]

        # Next we load all the tool fragments
        tool_mapping_frags = {}
        for mapping_fn in glob.iglob(
            os.path.join(MAPPING_DIR, "tool-data-frag-*.json")
        ):
            m = self._fpat.match(os.path.basename(mapping_fn))
            toolname = m.group("toolname")
            if self.known_tool_handlers is not None:
                if toolname not in self.known_tool_handlers:
                    raise MappingFileError(
                        "Unsupported tool '{}' mapping file {}".format(
                            toolname, mapping_fn
                        )
                    )
            mapping = self._load_json(mapping_fn)
            try:
                idxver = mapping["_meta"]["version"]
            except KeyError:
                raise MappingFileError(
                    "{} mapping missing _meta field in {}".format(key, mapping_fn)
                )
            if self._dbg > 5:
                print(
                    "fetch_mapping: {} -- {}\n{}\n".format(
                        mapping_fn,
                        toolname,
                        json.dumps(mapping, indent=4, sort_keys=True),
                    )
                )
            del mapping["_meta"]
            tool_mapping_frags[toolname] = mapping
            self.versions[ip["idxname"].format(tool=toolname)] = idxver

        tool_settings = self._load_json(os.path.join(SETTING_DIR, "tool-data.json"))

        for toolname, frag in tool_mapping_frags.items():
            tool_mapping = copy.deepcopy(skel)
            idxname = ip["idxname"].format(tool=toolname)
            idxver = self.versions[idxname]
            tool_mapping["_meta"] = dict(version=self.versions[idxname])
            tool_mapping["properties"][toolname] = frag
            tool_template_name = ip["template_name"].format(
                prefix=self.idx_prefix, version=idxver, idxname=idxname
            )
            tool_template_body = dict(
                index_patterns=ip["template_pat"].format(
                    prefix=self.idx_prefix,
                    version=self.versions[idxname],
                    idxname=idxname,
                ),
                settings=tool_settings,
                mappings=tool_mapping,
            )
            self.templates[tool_template_name] = tool_template_body

        # Add a standard "authorization" sub-document into each of the
        # document templates we've collected. With the single exception
        # of the server reports template, which isn't owned by any
        # user.
        for name, body in self.templates.items():
            if name != server_reports_template_name:
                body["mappings"]["properties"]["authorization"] = {
                    "properties": {
                        "owner": {"type": "keyword"},
                        "access": {"type": "keyword"},
                    }
                }

        self.counters = Counter()

    index_patterns = {
        "result-data": {
            "idxname": "result-data",
            "template_name": "{prefix}.v{version}.{idxname}",
            "template_pat": "{prefix}.v{version}.{idxname}.*",
            "template": "{prefix}.v{version}.{idxname}.{year}-{month}-{day}",
            "desc": "Daily result data (any data generated by the"
            " benchmark) for all pbench result tar balls;"
            " e.g prefix.v0.result-data.YYYY-MM-DD",
        },
        "result-data-sample": {
            "idxname": "result-data-sample",
            "template_name": "{prefix}.v{version}.{idxname}",
            "template_pat": "{prefix}.v{version}.{idxname}.*",
            "template": "{prefix}.v{version}.{idxname}.{year}-{month}-{day}",
            "desc": "Daily result data (any data generated by the"
            " benchmark) for all pbench result tar balls;"
            " e.g prefix.v0.result-data-sample.YYYY-MM-DD",
        },
        "run": {
            "idxname": "run-data",
            "template_name": "{prefix}.v{version}.{idxname}",
            "template_pat": "{prefix}.v{version}.{idxname}.*",
            "template": "{prefix}.v{version}.{idxname}.{year}-{month}",
            "desc": "Monthly pbench run metadata for index tar balls;"
            " contains directories, file names, and their size,"
            " permissions, etc.; e.g. prefix.v0.run.YYYY-MM",
        },
        "run-toc-entry": {
            "idxname": "run-toc",
            "template_name": "{prefix}.v{version}.{idxname}",
            "template_pat": "{prefix}.v{version}.{idxname}.*",
            "template": "{prefix}.v{version}.{idxname}.{year}-{month}",
            "desc": "Monthly table of contents metadata for index tar"
            " balls; contains directories, file names, and their size,"
            " permissions, etc.; e.g. prefix.v0.run.YYYY-MM",
        },
        "server-reports": {
            "idxname": "server-reports",
            "template_name": "{prefix}.v{version}.{idxname}",
            "template_pat": "{prefix}.v{version}.{idxname}.*",
            "template": "{prefix}.v{version}.{idxname}.{year}-{month}",
            "desc": "Monthly pbench server status reports for all"
            " cron jobs; e.g. prefix.v0.server-reports.YYYY-MM",
        },
        "tool-data": {
            "idxname": "tool-data-{tool}",
            "template_name": "{prefix}.v{version}.{idxname}",
            "template_pat": "{prefix}.v{version}.{idxname}.*",
            "template": "{prefix}.v{version}.{idxname}.{year}-{month}-{day}",
            "desc": "Daily tool data for all tools land in indices"
            " named by tool; e.g. prefix.v0.tool-data-iostat.YYYY-MM-DD",
        },
    }

    def dump_idx_patterns(self):
        patterns = self.index_patterns
        pattern_names = [idx for idx in patterns]
        pattern_names.sort()
        for idx in pattern_names:
            if idx != "tool-data":
                idxname = patterns[idx]["idxname"]
                print(
                    patterns[idx]["template"].format(
                        prefix=self.idx_prefix,
                        version=self.versions[idx],
                        idxname=idxname,
                        year="YYYY",
                        month="MM",
                        day="DD",
                    )
                )
            else:
                tool_names = [
                    tool
                    for tool in self.known_tool_handlers
                    if self.known_tool_handlers[tool] is not None
                ]
                tool_names.sort()
                for tool_name in tool_names:
                    idxname = patterns[idx]["idxname"].format(tool=tool_name)
                    print(
                        patterns[idx]["template"].format(
                            prefix=self.idx_prefix,
                            version=self.versions[idxname],
                            idxname=idxname,
                            year="YYYY",
                            month="MM",
                            day="DD",
                        )
                    )
            print("{}\n".format(patterns[idx]["desc"]))
        sys.stdout.flush()

    def dump_templates(self):
        template_names = [name for name in self.templates]
        template_names.sort()
        for name in template_names:
            print(
                "\n\nTemplate: {}\n\n{}\n".format(
                    name, json.dumps(self.templates[name], indent=4, sort_keys=True)
                )
            )
        sys.stdout.flush()

    def update_templates(self, es, target_name=None):
        """Push the various Elasticsearch index templates required by pbench.
        """
        if target_name is not None:
            idxname = self.index_patterns[target_name]["idxname"]
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
                _beg, _end, _retries, _stat = pyesbulk.put_template(
                    es,
                    name,
                    "pbench-{}".format(name.split(".")[2]),
                    self.templates[name],
                )
            except Exception as e:
                self.counters["put_template_failures"] += 1
                raise TemplateError(e)
            else:
                successes += 1
                if beg is None:
                    beg = _beg
                end = _end
                retries += _retries
        log_action = self.logger.warning if retries > 0 else self.logger.debug
        log_action(
            "done templates (start ts: {}, end ts: {}, duration: {:.2f}s,"
            " successes: {:d}, retries: {:d})",
            tstos(beg),
            tstos(end),
            end - beg,
            successes,
            retries,
        )

    def generate_index_name(self, template_name, source, toolname=None):
        """Return a fully formed index name given its template, prefix, source
        data (for an @timestamp field) and an optional tool name."""
        try:
            template = self.index_patterns[template_name]["template"]
            idxname_tmpl = self.index_patterns[template_name]["idxname"]
        except KeyError as e:
            self.counters["invalid_template_name"] += 1
            raise Exception("Invalid template name, '{}': {}".format(template_name, e))
        if toolname is not None:
            idxname = idxname_tmpl.format(tool=toolname)
            try:
                version = self.versions[idxname]
            except KeyError as e:
                self.counters["invalid_tool_index_name"] += 1
                raise Exception(
                    "Invalid tool index name for version, '{}':"
                    " {}".format(idxname, e)
                )
        else:
            idxname = idxname_tmpl
            try:
                version = self.versions[template_name]
            except KeyError as e:
                self.counters["invalid_template_name"] += 1
                raise Exception(
                    "Invalid index template name for version,"
                    " '{}': {}".format(idxname, e)
                )
        try:
            ts_val = source["@timestamp"]
        except KeyError:
            self.counters["ts_missing_at_timestamp"] += 1
            raise BadDate(f"missing @timestamp in a source document: {source!r}")
        except TypeError as e:
            self.counters["bad_source"] += 1
            raise Exception(f"Failed to generate index name, {e}, source: {source!r}")
        year, month, day = ts_val.split("T", 1)[0].split("-")[0:3]
        return template.format(
            prefix=self.idx_prefix,
            version=version,
            idxname=idxname,
            year=year,
            month=month,
            day=day,
        )
