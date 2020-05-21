"""
Module for mocking out behaviors of V1 Elasticsearch.
"""

import sys
import json
from collections import Counter


class MockElasticsearch(object):
    """A simple mock for the V1 Elasticsearch client object. We really just
    duck-type it, only providing names for attributes we use.  It is not complete
    by any stretch of the imagination.
    """

    def __init__(self, hosts, max_retries=None):
        self.hosts = hosts
        self.max_retries = max_retries
        self.mpt = _MockPutTemplate()
        # We pass a hard-coded value of 15 to the constructor for
        # _MockStreamingBulk objects to make sure we only track at most 15
        # objects per index for reporting and analysis.  We don't create a
        # constant for this value because the current unit test gold files
        # capture the JSON dump of the actions, which is expected to be 15
        # per index.
        self.msb = _MockStreamingBulk(15, self.mpt)
        self.indices = _MockObject(
            put_template=self.mpt.put_template, get_template=self.mpt.get_template
        )
        self.mockstrm = _MockObject(streaming_bulk=self.msb.streaming_bulk)


class _MockObject(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class _MockPutTemplate(object):
    def __init__(self):
        self.mock_collected_templates = {}

    def get_template(self, *args, **kwargs):
        assert "name" in kwargs, "Mock'd get_template missing 'name' in kwargs"
        name = kwargs["name"]
        mapping_name = "pbench-{}".format(name.split(".")[2])
        tmpl = {}
        tmpl[name] = {"mappings": {}}
        tmpl[name]["mappings"][mapping_name] = {"_meta": {"version": 0}}
        return tmpl

    def put_template(self, *args, **kwargs):
        assert (
            "name" in kwargs and "body" in kwargs
        ), "Mock'd put_template missing 'name' and/or 'body' in kwargs"
        name = kwargs["name"]
        assert (
            name not in self.mock_collected_templates
        ), f"Duplicate template name, '{name}'"
        self.mock_collected_templates[name] = kwargs["body"]
        return None

    def report(self):
        self.mock_mappings = {}
        names = [name for name in self.mock_collected_templates.keys()]
        names.sort()
        for name in names:
            print("Template: ", name)
            body = self.mock_collected_templates[name]
            for name, mapping in body["mappings"].items():
                assert name not in self.mock_mappings, (
                    "Duplicate mapping name encountered:"
                    " {} ({!r})".format(name, self.mock_mappings.keys())
                )
                self.mock_mappings[name] = mapping
        sys.stdout.flush()


class _MockStreamingBulk(object):
    """Mock out helpers.streaming_bulk for unit testing purposes.

    Construct this object passing it the maximum number of actions we should
    capture for reporting purposes, and the _MockPutTemplate() instance
    previously created so that we can report the previously loaded templates,
    and check the actions against the mappings in each template.
    """

    def __init__(self, max_actions, mpt):
        self.max_actions = max_actions
        self.mpt = mpt
        self.reset()

    def reset(self):
        self.actions_l = []
        self.duplicates_tracker = Counter()
        self.index_tracker = Counter()
        self.dupes_by_index_tracker = Counter()

    @staticmethod
    def streaming_bulk(es, actions, **kwargs):
        assert isinstance(es, MockElasticsearch), "Unexpected es object: {!r}".format(
            es
        )
        msb = es.msb
        # First dump the template report before we continue
        msb.mpt.report()
        for action in actions:
            msb.duplicates_tracker[action["_id"]] += 1
            dcnt = msb.duplicates_tracker[action["_id"]]
            if dcnt == 2:
                msb.dupes_by_index_tracker[action["_index"]] += 1
            msb.index_tracker[action["_index"]] += 1
            if msb.index_tracker[action["_index"]] <= msb.max_actions:
                msb.actions_l.append(action)
                msb.validate_type(action)
            resp = {}
            resp[action["_op_type"]] = {"_id": action["_id"]}
            if dcnt > 2:
                # Report each duplicate
                resp[action["_op_type"]]["status"] = 409
                ok = False
            else:
                # For now, all other docs are considered successful
                resp[action["_op_type"]]["status"] = 200
                ok = True
            yield ok, resp
        msb.report()

    def validate_type(self, action):
        """Crude approach to validating the constructed dictionaries ahead of
        being converted to JSON.
        """
        the_type = action["_type"]
        try:
            the_mapping = self.mpt.mock_mappings[the_type]
        except KeyError:
            print(
                "Could not find document type '{}' in {!r}".format(
                    the_type, list(self.mpt.mock_mappings.keys())
                )
            )
            return False

        the_source = action["_source"]
        return self._check_fields(the_source, the_mapping)

    @staticmethod
    def _check_fields(source, mapping):
        """Recursively descend the source dictionary hierarchy, descending
        the mapping hiearchy at the same time, and validate each source
        entry has a proper mapping for it.

        Note that we don't raise an exception, just emit a text string to
        stdout so that unit tests will fail to compare properly against
        their gold files.

        """
        ret_val = True
        if "properties" not in mapping:
            if isinstance(source, dict):
                # Given the source element is a dictionary, the mapping
                # element should contain a "properties" element containing
                # the definition of all the sub fields.
                print("Properties element not a dictionary")
                return False
            try:
                mtype = mapping["type"]
            except KeyError:
                # All mappings should have a type at this point.
                print("Missing type")
                return False
            if isinstance(source, list):
                if mtype == "string":
                    # If a list only contains strings then to Elasticsearch it
                    # is as if the strings were all concatenated together
                    # separated by spaces and tokenized.
                    for item in source:
                        if not isinstance(item, str):
                            print(
                                "List contains an element of type, {}, when"
                                " expecting only strings".format(type(item))
                            )
                            return False
                    return True
                elif mtype != "nested":
                    # Fail first because the mapping type is not 'nested'
                    # for a list object.
                    print("Type list not nested")
                    return False
                # All lists should be lists of dictionaries, but because
                # we don't have a 'properties' element in the mapping we
                # can't proceed.
                print("List type without a properties entry")
                return False
            if mtype in ("string", "date", "ip"):
                if source is not None and not isinstance(source, str):
                    print("Expected 'str'")
                    ret_val = False
            elif mtype in ("integer", "long"):
                if source is not None and not isinstance(source, int):
                    print("Expected 'int'")
                    ret_val = False
            elif mtype in ("float", "double"):
                if (
                    source is not None
                    and not isinstance(source, float)
                    and not isinstance(source, int)
                ):
                    print("Expected 'float' or 'int'")
                    ret_val = False
            elif mtype in ("boolean",):
                if source is not None and not isinstance(source, bool):
                    print("Expected 'bool'")
                    ret_val = False
            else:
                print("Unrecognized type: {}".format(mtype))
                ret_val = False
            return ret_val
        if isinstance(source, list):
            try:
                mtype = mapping["type"]
                props = mapping["properties"]
            except KeyError:
                # All mappings should have a type at this point, and because
                # it is a list it should have a set of properties.
                print("Missing type and properties")
                return False
            if mtype != "nested":
                print("The mapping type is not 'nested' for a list object")
                return False
            for idx, item in enumerate(source):
                if not isinstance(item, dict):
                    print("Item [{:d}] in list must be a dictionary".format(idx))
                    ret_val = False
                for key in item.keys():
                    try:
                        sub_mapping = props[key]
                    except KeyError:
                        print(
                            "A source does not conform to mapping, {}: key '{}' not found in {!r}".format(
                                mtype, key, sorted(set(props.keys()))
                            )
                        )
                        ret_val = False
                    if not _MockStreamingBulk._check_fields(item[key], sub_mapping):
                        print(
                            "A source does not conform to mapping, {}: key '{}' has bad mapping".format(
                                mtype, key
                            )
                        )
                        ret_val = False
        elif not isinstance(source, dict):
            # The source is not a dictionary, yet the mapping has a
            # properties entry which requires the source element be a
            # dictionary.
            print("Unexpected source element type, not a dict or a list")
            ret_val = False
        else:
            # We have a properties element with a dictionary in the
            # source.
            ret_val = True
            for key in source.keys():
                sub_source = source[key]
                try:
                    sub_mapping = mapping["properties"][key]
                except KeyError:
                    print(
                        "A source does not conform to mapping: key '{}' not found in {!r}".format(
                            key, sorted(set(mapping["properties"].keys()))
                        )
                    )
                    ret_val = False
                else:
                    if not _MockStreamingBulk._check_fields(sub_source, sub_mapping):
                        print(
                            "A source does not conform to mapping: key '{}' has bad mapping".format(
                                key
                            )
                        )
                        ret_val = False
        return ret_val

    def report(self):
        for idx in sorted(self.index_tracker.keys()):
            print("Index: ", idx, self.index_tracker[idx])
        total_dupes = 0
        total_multi_dupes = 0
        for docid in self.duplicates_tracker:
            total_dupes += (
                self.duplicates_tracker[docid]
                if self.duplicates_tracker[docid] > 1
                else 0
            )
            if self.duplicates_tracker[docid] >= 2:
                total_multi_dupes += 1
        if total_dupes > 0:
            print("Duplicates: ", total_dupes, "Multiple dupes: ", total_multi_dupes)
        for idx in sorted(self.dupes_by_index_tracker.keys()):
            print("Index dupes: ", idx, self.dupes_by_index_tracker[idx])
        print("len(actions) = {}".format(len(self.actions_l)))
        print(json.dumps(self.actions_l, indent=4, sort_keys=True))
        sys.stdout.flush()
        self.reset()
