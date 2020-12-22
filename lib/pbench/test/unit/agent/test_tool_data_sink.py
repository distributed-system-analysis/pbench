"""Tests for the Tool Data Sink module.
"""

import logging
import pytest
import shutil
import time

from http import HTTPStatus
from io import BytesIO
from pathlib import Path
from threading import Condition, Lock, Thread
from unittest.mock import patch
from wsgiref.simple_server import WSGIRequestHandler

from pbench.agent import tool_data_sink
from pbench.agent.tool_data_sink import (
    BenchmarkRunDir,
    ToolDataSinkError,
    DataSinkWsgiServer,
)


class TestBenchmarkRunDir:
    """Verify the Tool Data Sink BenchmarkRunDir class.
    """

    @pytest.fixture
    def cleanup_tmp(self, pytestconfig):
        TMP = Path(pytestconfig.cache.get("TMP", None))
        self.int_pb_run = TMP / "pbench-run-int"
        self.ext_pb_run = TMP / "pbench-run-ext"
        yield
        try:
            shutil.rmtree(self.int_pb_run)
        except Exception as exc:
            print(exc)
        try:
            shutil.rmtree(self.ext_pb_run)
        except Exception as exc:
            print(exc)

    def test_validate(self, cleanup_tmp):
        """test_validate - verify the behavior of the validate() using both an
        internal - external difference and when the internal and external
        directories are the same.

        This implicitly tests the constructor as well.
        """
        self.int_pb_run.mkdir()
        ext_bm_rd = self.int_pb_run / "bm-run-dir"
        ext_bm_rd.mkdir()
        brd = BenchmarkRunDir(str(ext_bm_rd), str(self.int_pb_run))
        assert str(ext_bm_rd) == str(brd)

        valpre = ext_bm_rd / "valid-prefix"
        valpre.mkdir()
        obj = brd.validate(str(valpre))
        assert str(valpre) == str(obj)

        with pytest.raises(brd.Prefix):
            brd.validate("/not/a/valid-prefix")

        self.ext_pb_run.mkdir()
        ext_bm_rd = self.ext_pb_run / "bm-run-dir"
        ext_bm_rd.mkdir()
        brd = BenchmarkRunDir(str(ext_bm_rd), str(self.int_pb_run))

        valpre = ext_bm_rd / "not-a-prefix"
        with pytest.raises(brd.Exists):
            brd.validate(valpre)

    def test_constructor_errors(self, cleanup_tmp):
        """test_constructor_errors - verify errors are properly raised during
        the execution of the constructor.
        """
        self.int_pb_run.mkdir()

        ext_bm_rd = self.int_pb_run / "bm-run-dir"
        ext_bm_rd.write_text("Should be a directory!")
        with pytest.raises(ToolDataSinkError) as exc:
            BenchmarkRunDir(str(ext_bm_rd), str(self.int_pb_run))
        exp_err = f"Run directory parameter, '{ext_bm_rd}', must be a real directory."
        assert exp_err == str(exc.value)
        ext_bm_rd.unlink()

        # NOTE: in a container the "internal" pbench run directory must exist,
        # the external pbench run directory does not exist from within the
        # container.
        ext_bm_rd = self.ext_pb_run / "bm-run-dir"
        int_bm_rd = self.int_pb_run / "bm-run-dir"
        int_bm_rd.mkdir()
        with pytest.raises(ToolDataSinkError) as exc:
            BenchmarkRunDir(str(ext_bm_rd), str(self.int_pb_run))
        exp_err = (
            f"Run directory parameter, '{ext_bm_rd}', must be an existing"
            f" directory ('{self.ext_pb_run}/.path' not found, '"
        )
        assert str(exc.value).startswith(exp_err)

        self.ext_pb_run.mkdir()
        dot_path = self.int_pb_run / ".path"
        dot_path_contents = f"{self.ext_pb_run}-mismatch"
        dot_path.write_text(dot_path_contents)
        with pytest.raises(ToolDataSinkError) as exc:
            BenchmarkRunDir(str(ext_bm_rd), str(self.int_pb_run))
        exp_err = (
            f"Run directory parameter, '{ext_bm_rd}', must be an existing"
            f" directory (.path contents mismatch, .path='{dot_path_contents}'"
            f" != '{self.ext_pb_run}')."
        )
        assert exp_err == str(exc.value)


def _test_app(environ, start_response):
    start_response(
        "200 OK",
        [("Content-Type", "text/plain"), ("Date", "Fri, 12 Feb 2021 23:35:42 UTC")],
    )
    return [b"Hello, world! 42"]


class TestDataSinkWsgiServer:
    """Verify the DataSinkWsgiServer wrapper class.
    """

    def test_constructor(self):
        """test_constructor - verify the DataSinkWsgiServer constructor.
        """
        with pytest.raises(Exception) as exc:
            DataSinkWsgiServer()
        assert "DataSinkWsgiServer requires a logger" == str(exc.value)

        wsgi = DataSinkWsgiServer(
            host="host.example.com", port="42", logger="__logger__"
        )
        assert wsgi.options.get("handler_class", "missing") != "missing"
        klass = wsgi.options.get("handler_class")
        assert isinstance(klass, type(WSGIRequestHandler))
        assert wsgi._server is None
        assert wsgi._err_code is None
        assert wsgi._err_text is None
        assert isinstance(wsgi._lock, type(Lock()))
        assert isinstance(wsgi._cv, type(Condition()))
        assert wsgi._logger == "__logger__"

    def test_log_methods(self, caplog):
        logger = logging.getLogger("test_log_methods")
        wsgi_server = DataSinkWsgiServer(
            host="host.example.com", port="42", logger=logger
        )
        wrh = wsgi_server.options["handler_class"]
        # This forces the base WSGI methods to not buffer writes.
        wrh.wbufsize = 1

        class MockBytesIO(BytesIO):
            def close(self, *args, **kwargs):
                self._saved_value = self.getvalue()
                super().close(*args, **kwargs)

        class MockSocket:
            def getsockname(self):
                return ("sockname",)

        class MockRequest:
            _sock = MockSocket()

            def __init__(self, path):
                self._path = path

            def makefile(self, *args, **kwargs):
                if args[0] == "rb":
                    return MockBytesIO(b"GET %s HTTP/1.1" % self._path)
                elif args[0] == "wb":
                    return MockBytesIO(b"")
                else:
                    raise ValueError(
                        "MockRequest: unrecognized file type", args, kwargs
                    )

        class MockServer:
            def __init__(self):
                self.base_environ = {}

            def get_app(self):
                return _test_app

        mock_server = MockServer()

        # We perform all these above mock infrastructure just to get a usable
        # DataSinkWsgiRequestHandler() object.  The MockRequest() mimics a
        # single request being handled, where a response is generated, and
        # captured in the handlers "wfile" attribute value.  This one request
        # will also emit one informational log.
        handler = wrh(MockRequest(b"/"), (0, 0), mock_server)
        assert handler.wfile._saved_value.startswith(b"HTTP/1.0 200 OK")
        assert handler.wfile._saved_value.endswith(b"Hello, world! 42")
        assert caplog.records[0].levelname == "INFO"
        assert caplog.records[0].message == '0 - - "GET / HTTP/1.1" 200 16'

        # Now that we have this handler object, we can directly invoke the
        # other logging methods to verify their behavior.
        handler.log_error("test error %d %s", 42, "43")
        assert caplog.records[1].levelname == "ERROR"
        assert caplog.records[1].message == "0 - - test error 42 43"
        handler.log_message("test msg %d %s", 42, "43")
        assert caplog.records[2].levelname == "WARNING"
        assert caplog.records[2].message == "0 - - test msg 42 43"
        handler.log_request(code=HTTPStatus(404), size=42)
        assert caplog.records[3].levelname == "INFO"
        assert caplog.records[3].message == '0 - - "GET / HTTP/1.1" 404 42'

    class MockServer:
        def __init__(self, host, port, app, *args, **kwargs):
            self.host = host
            self.port = port
            self.app = app
            self.args = args
            self.kwargs = kwargs
            self.serve_forever_called = False
            self.shutdown_called = False
            if self.host.startswith("oserror"):
                raise OSError(42, "oserror")
            elif self.host.startswith("exception"):
                raise Exception("exception")

        def shutdown(self):
            self.shutdown_called = True

        def serve_forever(self):
            self.serve_forever_called = True

    def test_run(self, caplog):
        """test_run - verify code paths of run method directly.

        NOTE: We are not using threads to do this.  Instead we are mocking out
        the `make_server` call to create a fake server that we control that
        does nothing when "serve_forever" is called.
        """
        logger = logging.getLogger("test_run")
        wsgi_server = DataSinkWsgiServer(
            host="host.example.com", port="42", logger=logger
        )
        mocked_servers = []

        def mock_make_server(host, port, app, *args, **kwargs):
            mocked_server = self.MockServer(host, port, app, *args, **kwargs)
            mocked_servers.append(mocked_server)
            return mocked_server

        with patch.object(tool_data_sink, "make_server", mock_make_server):
            # First we invoke the "run" method once to let it execute normally.
            try:
                wsgi_server.run(_test_app)
            except Exception as exc:
                pytest.fail(f"WSGI server failed with an exception, {exc}")
            else:
                # Retrieve the internal server object that we created, and
                # verify that it is created as expected, and that
                # "serve_forever" was called.
                mock_server = mocked_servers[0]
                assert wsgi_server._server is mock_server
                assert wsgi_server._err_code == 0
                assert wsgi_server._err_text is None
                assert mock_server.host == "host.example.com"
                assert mock_server.port == 42
                assert mock_server.app is _test_app
                assert mock_server.args == ()
                klass = mock_server.kwargs.get("handler_class")
                assert isinstance(klass, type(WSGIRequestHandler))
                assert mock_server.serve_forever_called
                # The success path of "run" should have emitted three debug
                # messages.
                assert len(caplog.records) == 3
                assert caplog.records[0].levelname == "DEBUG"
                assert (
                    caplog.records[0].message == "Making tool data sink WSGI server ..."
                )
                assert caplog.records[1].levelname == "DEBUG"
                assert caplog.records[1].message == "Successfully created WSGI server"
                assert caplog.records[2].levelname == "DEBUG"
                assert (
                    caplog.records[2].message
                    == "Running tool data sink WSGI server ..."
                )
            with pytest.raises(AssertionError) as exc:
                # Call it again to verify the assertion fires
                wsgi_server.run(_test_app)
            assert "'run' method called twice" in str(exc.value), f"{exc.value}"
            # No logs should have been emitted.
            assert len(caplog.records) == 3

    def test_stop_and_wait(self, caplog):
        """test_stop_and_wait - verify the operation of run() in conjunction
        with stop() and wait() methods from separate threads.

        There are a number of scenarios for the order of operations between
        threads that we need to test.  We list them here using "MainThr" as the
        name of the "main thread" which _creates_ the WSGI thread, and "WsgiThr"
        as the name of the created WSGI thread invoking the "run" method.

        References:
            .wait() called in
                .stop() method
                __enter__() method
            .stop() called in
                __exit__() method

        Scenario A:

          * MainThr creates WSGI thread (WsgiThr not running)
          * MainThr calls stop()
          * WsgiThr starts running
          * WsgiThr reports err_code == 0

        Scenario B:

          * MainThr creates WSGI thread
          * WsgiThr starts running
          * WsgiThr reports err_code == 0
          * MainThr calls stop()

        Scenario C:

          * MainThr creates WSGI thread (WsgiThr not running)
          * MainThr calls stop()
          * WsgiThr starts running
          * WsgiThr reports err_code > 0

        Scenario D:

          * MainThr creates WSGI thread
          * WsgiThr starts running
          * WsgiThr reports err_code > 0
          * MainThr calls stop()

        Scenario E:

          * MainThr creates WSGI thread (WsgiThr not running)
          * MainThr calls stop()
          * WsgiThr starts running
          * WsgiThr reports err_code < 0

        Scenario F:

          * MainThr creates WSGI thread
          * WsgiThr starts running
          * WsgiThr reports err_code < 0
          * MainThr calls stop()
        """

        def wsgi_run(scenario, wsgi_server, trace):
            ret_val = None
            if scenario in ("A", "C", "E"):
                time.sleep(0.1)
            try:
                trace.append("WsgiThr - run")
                wsgi_server.run(_test_app)
            except Exception as exc:
                ret_val = exc
            return ret_val

        def do_wait(scenario, wsgi_server, trace):
            if scenario in ("B", "D", "F"):
                time.sleep(0.1)
            trace.append("MainThr - wait")
            err_text, err_code = wsgi_server.wait()
            return err_text, err_code

        def do_stop(scenario, wsgi_server, trace):
            if scenario in ("B", "D", "F"):
                time.sleep(0.1)
            trace.append("MainThr - stop")
            wsgi_server.stop()

        # The host name prefix directs the MockServer class to behave by
        # raising an OSError or Exception base on the name.
        hostnames = dict(
            A="host.example.com",
            B="host.example.com",
            C="oserror.example.com",
            D="oserror.example.com",
            E="exception.example.com",
            F="exception.example.com",
        )
        caplog_idx = 0
        logger = logging.getLogger("test_run")
        for scenario in ["A", "B", "C", "D", "E", "F"]:
            wsgi_server = DataSinkWsgiServer(
                host=hostnames[scenario], port="42", logger=logger
            )
            mocked_servers = []

            def mock_make_server(host, port, app, *args, **kwargs):
                mocked_server = self.MockServer(host, port, app, *args, **kwargs)
                mocked_servers.append(mocked_server)
                return mocked_server

            with patch.object(tool_data_sink, "make_server", mock_make_server):
                trace = []
                wsgithr = Thread(target=wsgi_run, args=(scenario, wsgi_server, trace))
                wsgithr.start()
                err_text, err_code = do_wait(scenario, wsgi_server, trace)
                wsgithr.join()
                assert caplog.records[caplog_idx].levelname == "DEBUG"
                assert (
                    caplog.records[caplog_idx].message
                    == "Making tool data sink WSGI server ..."
                )
                caplog_idx += 1
                if scenario in ("A", "B"):
                    mock_server = mocked_servers[0]
                    assert mock_server.serve_forever_called
                    assert not mock_server.shutdown_called
                    assert err_code == 0
                    assert err_text is None
                    assert caplog.records[caplog_idx].levelname == "DEBUG"
                    assert (
                        caplog.records[caplog_idx].message
                        == "Successfully created WSGI server"
                    )
                    caplog_idx += 1
                    assert caplog.records[caplog_idx].levelname == "DEBUG"
                    assert (
                        caplog.records[caplog_idx].message
                        == "Running tool data sink WSGI server ..."
                    )
                    caplog_idx += 1
                elif scenario in ("C", "D"):
                    assert len(mocked_servers) == 0
                    assert err_code == 42
                    assert err_text == "[Errno 42] oserror"
                    # Only 1 log message is emitted when OSErrors are encountered
                else:
                    assert scenario in ("E", "F")
                    assert len(mocked_servers) == 0
                    assert err_code == -1
                    assert err_text == "exception"
                    assert caplog.records[caplog_idx].levelname == "ERROR"
                    assert (
                        caplog.records[caplog_idx].message
                        == "Unexpected error in WSGI server"
                    )
                    caplog_idx += 1
                assert len(caplog.records) == caplog_idx

        # Now we test two cases for the stop() method
        for scenario in ["A", "E"]:
            wsgi_server = DataSinkWsgiServer(
                host=hostnames[scenario], port="42", logger=logger
            )
            mocked_servers = []

            def mock_make_server(host, port, app, *args, **kwargs):
                mocked_server = self.MockServer(host, port, app, *args, **kwargs)
                mocked_servers.append(mocked_server)
                return mocked_server

            with patch.object(tool_data_sink, "make_server", mock_make_server):
                trace = []
                wsgithr = Thread(target=wsgi_run, args=(scenario, wsgi_server, trace))
                wsgithr.start()
                do_stop(scenario, wsgi_server, trace)
                wsgithr.join()
                assert caplog.records[caplog_idx].levelname == "DEBUG"
                assert (
                    caplog.records[caplog_idx].message
                    == "Making tool data sink WSGI server ..."
                )
                caplog_idx += 1
                if scenario == "A":
                    mock_server = mocked_servers[0]
                    assert mock_server.serve_forever_called
                    assert mock_server.shutdown_called
                    caplog_idx += 2
                else:
                    assert scenario == "E"
                    assert len(mocked_servers) == 0
                    caplog_idx += 1
                assert len(caplog.records) == caplog_idx
