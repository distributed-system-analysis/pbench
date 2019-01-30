"""
Simple module level convenience functions.
"""

import sys, os, time, json, errno, logging, math

from random import SystemRandom
from collections import Counter, deque
from urllib3 import exceptions as ul_excs
try:
    from elasticsearch1 import VERSION as es_VERSION, helpers, exceptions as es_excs
except ImportError:
    from elasticsearch import VERSION as es_VERSION, helpers, exceptions as es_excs


def tstos(ts=None):
    return time.strftime("%Y-%m-%dT%H:%M:%S-%Z", time.localtime(ts))


_r = SystemRandom()
_MAX_SLEEP_TIME = 120
_MAX_ERRMSG_LENGTH = 16384

def calc_backoff_sleep(backoff):
    global _r
    b = math.pow(2, backoff)
    return _r.uniform(0, min(b, _MAX_SLEEP_TIME))


class MockPutTemplate(object):
    def __init__(self):
        self.name = None

    def put_template(self, *args, **kwargs):
        assert 'name' in kwargs and 'body' in kwargs
        name = kwargs['name']
        if self.name is None:
            self.name = name
        else:
            assert self.name == name
        return None

    def report(self):
        print("Template: ", self.name)


def es_put_template(es, name=None, body=None):
    assert name is not None and body is not None
    if not es:
        mock = MockPutTemplate()
        def _ts():
            return 0
        _do_ts = _ts
        _put_template = mock.put_template
    else:
        mock = None
        _do_ts = time.time
        _put_template = es.indices.put_template
        # FIXME: we should just change these two loggers to write to a
        # file instead of setting the logging level up so high.
        logging.getLogger("urllib3").setLevel(logging.FATAL)
        logging.getLogger("elasticsearch1").setLevel(logging.FATAL)

    retry = True
    retry_count = 0
    backoff = 1
    beg, end = _do_ts(), None
    while retry:
        try:
            _put_template(name=name, body=body)
        except es_excs.TransportError as exc:
            # Only retry on certain 500 errors
            if not exc.status in [500, 503, 504]:
                raise
            time.sleep(calc_backoff_sleep(backoff))
            backoff += 1
            retry_count += 1
        except es_excs.ConnectionError as exc:
            # We retry all connection errors
            time.sleep(calc_backoff_sleep(backoff))
            backoff += 1
            retry_count += 1
        else:
            retry = False
    end = _do_ts()

    if mock:
        mock.report()
    return beg, end, retry_count


class MockStreamingBulk(object):
    def __init__(self, max_actions):
        self.max_actions = max_actions
        self.actions_l = []
        self.duplicates_tracker = Counter()
        self.index_tracker = Counter()
        self.dupes_by_index_tracker = Counter()

    def our_streaming_bulk(self, es, actions, **kwargs):
        assert es == None
        for action in actions:
            self.duplicates_tracker[action['_id']] += 1
            dcnt = self.duplicates_tracker[action['_id']] 
            if dcnt == 2:
                self.dupes_by_index_tracker[action['_index']] += 1
            self.index_tracker[action['_index']] += 1
            if self.index_tracker[action['_index']] <= self.max_actions:
                self.actions_l.append(action)
            resp = {}
            resp[action['_op_type']] = { '_id': action['_id'] }
            if dcnt > 2:
                # Report each duplicate
                resp[action['_op_type']]['status'] = 409
                ok = False
            else:
                # For now, all other docs are considered successful
                resp[action['_op_type']]['status'] = 200
                ok = True 
            yield ok, resp

    def report(self):
        for idx in sorted(self.index_tracker.keys()):
            print("Index: ", idx, self.index_tracker[idx])
        total_dupes = 0
        total_multi_dupes = 0
        for docid in self.duplicates_tracker:
            total_dupes += self.duplicates_tracker[docid] if self.duplicates_tracker[docid] > 1 else 0
            if self.duplicates_tracker[docid] >= 2:
                total_multi_dupes += 1
        if total_dupes > 0:
            print("Duplicates: ", total_dupes, "Multiple dupes: ", total_multi_dupes)
        for idx in sorted(self.dupes_by_index_tracker.keys()):
            print("Index dupes: ", idx, self.dupes_by_index_tracker[idx])
        print("len(actions) = {}".format(len(self.actions_l)))
        print(json.dumps(self.actions_l, indent=4, sort_keys=True))


# Always use "create" operations, as we also ensure each JSON document being
# indexed has an "_id" field, so we can tell when we are indexing duplicate
# data.
_op_type = "create"
# 100,000 minute timeout talking to Elasticsearch; basically we just don't
# want to timeout waiting for Elasticsearch and then have to retry, as that
# can add undue burden to the Elasticsearch cluster.
_request_timeout = 100000*60.0

def es_index(es, actions, errorsfp, dbg=0):
    """
    Now do the indexing specified by the actions.
    """
    global tstos
    if not es:
        # If we don't have an Elasticsearch client object, we assume this is
        # for unit tests or debugging, so we'll use our mocked out streaming
        # bulk method.
        mock = MockStreamingBulk(15)
        streaming_bulk = mock.our_streaming_bulk
        def _tstos(*args):
            return "1970-01-01T00:00:00-UTC"
        tstos = _tstos
        def _ts():
            return 0
        _do_ts = _ts
    else:
        mock = None
        streaming_bulk = helpers.streaming_bulk
        _do_ts = time.time
        # FIXME: we should just change these two loggers to write to a
        # file instead of setting the logging level up so high.
        logging.getLogger("urllib3").setLevel(logging.FATAL)
        logging.getLogger("elasticsearch1").setLevel(logging.FATAL)

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
            assert '_id' in cl_action
            assert '_index' in cl_action
            assert '_type' in cl_action
            assert _op_type == cl_action['_op_type']

            actions_deque.append((0, cl_action))   # Append to the right side ...
            yield cl_action
            # if after yielding an action some actions appear on the retry deque
            # start yielding those actions until we drain the retry queue.
            backoff = 1
            while len(actions_retry_deque) > 0:
                time.sleep(calc_backoff_sleep(backoff))
                retries_tracker['retries'] += 1
                retry_actions = []
                # First drain the retry deque entirely so that we know when we
                # have cycled through the entire list to be retried.
                while len(actions_retry_deque) > 0:
                    retry_actions.append(actions_retry_deque.popleft())
                for retry_count, retry_action in retry_actions:
                    actions_deque.append((retry_count, retry_action))   # Append to the right side ...
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

    streaming_bulk_generator = streaming_bulk(
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
            print("es_index: ERROR %r" % (e), file=sys.stderr)
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
                jsonstr = json.dumps({ "action": action, "ok": ok, "resp": resp, "retry_count": retry_count, "timestamp": tstos(_do_ts()) }, indent=4, sort_keys=True)
                print(jsonstr, file=errorsfp)
                errorsfp.flush()
                failures += 1
            else:
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
                    print("es_index: WARNING - retrying action \n%s" % (json.dumps(resp, indent=4)[:_MAX_ERRMSG_LENGTH]), file=sys.stderr)
                    actions_retry_deque.append((retry_count + 1, action))

    end = _do_ts()

    assert len(actions_deque) == 0
    assert len(actions_retry_deque) == 0

    if mock:
        mock.report()

    return (beg, end, successes, duplicates, failures, retries_tracker['retries'])
