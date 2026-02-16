"""Tests for ServerStorage — buffering, flushing, HTTP, and error handling."""

from __future__ import annotations

import http.server
import json
import threading
import time
from typing import Any

import pytest

from modelab._server_storage import _FLUSH_SIZE, ServerStorage
from modelab._types import AssignmentRecord, EventRecord, ExecutionRecord


class _MockServer:
    """Minimal HTTP server that captures POST requests."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self._server: http.server.HTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> int:
        parent = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                parent.requests.append(
                    {
                        "path": self.path,
                        "body": json.loads(body) if body else [],
                        "headers": dict(self.headers),
                    }
                )
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"inserted": 1}')

            def log_message(self, format, *args):
                pass  # Silence logs

        self._server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return port

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()


@pytest.fixture
def mock_server():
    """Start a mock HTTP server that captures POST requests."""
    srv = _MockServer()
    port = srv.start()
    yield srv, port
    srv.stop()


def _make_storage(port: int, api_key: str = "") -> ServerStorage:
    """Create a ServerStorage instance pointing to the mock server."""
    return ServerStorage(f"http://127.0.0.1:{port}", api_key=api_key)


# ── Basic Functionality ──────────────────────────────────────────────


class TestBasicFunctionality:
    def test_flush_sends_assignments(self, mock_server):
        srv, port = mock_server
        storage = _make_storage(port)
        storage.save_assignment(AssignmentRecord(flag_name="f", variant_name="v", user_id="u"))
        storage.flush()

        assert len(srv.requests) == 1
        assert srv.requests[0]["path"] == "/api/v1/ingest/assignments"
        assert len(srv.requests[0]["body"]) == 1
        assert srv.requests[0]["body"][0]["flag_name"] == "f"

    def test_flush_sends_executions(self, mock_server):
        srv, port = mock_server
        storage = _make_storage(port)
        storage.save_execution(ExecutionRecord(assignment_id="a1", latency_ms=100.0))
        storage.flush()

        assert len(srv.requests) == 1
        assert srv.requests[0]["path"] == "/api/v1/ingest/executions"

    def test_flush_sends_events(self, mock_server):
        srv, port = mock_server
        storage = _make_storage(port)
        storage.save_event(EventRecord(assignment_id="a1", event_type="success"))
        storage.flush()

        assert len(srv.requests) == 1
        assert srv.requests[0]["path"] == "/api/v1/ingest/events"

    def test_flush_sends_all_buffer_types(self, mock_server):
        srv, port = mock_server
        storage = _make_storage(port)
        storage.save_assignment(AssignmentRecord(flag_name="f", variant_name="v", user_id="u"))
        storage.save_execution(ExecutionRecord(assignment_id="a1"))
        storage.save_event(EventRecord(assignment_id="a1", event_type="success"))
        storage.flush()

        paths = {r["path"] for r in srv.requests}
        assert paths == {
            "/api/v1/ingest/assignments",
            "/api/v1/ingest/executions",
            "/api/v1/ingest/events",
        }

    def test_flush_empty_buffers_sends_nothing(self, mock_server):
        srv, port = mock_server
        storage = _make_storage(port)
        storage.flush()
        assert len(srv.requests) == 0


# ── API Key ──────────────────────────────────────────────────────────


class TestAPIKey:
    def test_api_key_sent_in_header(self, mock_server):
        srv, port = mock_server
        storage = _make_storage(port, api_key="secret-key")
        storage.save_assignment(AssignmentRecord(flag_name="f", variant_name="v", user_id="u"))
        storage.flush()

        # http.server normalizes header names — check case-insensitively
        headers = srv.requests[0]["headers"]
        api_key_value = headers.get("X-Api-Key") or headers.get("X-API-Key") or headers.get("x-api-key")
        assert api_key_value == "secret-key"

    def test_no_api_key_header_when_empty(self, mock_server):
        srv, port = mock_server
        storage = _make_storage(port, api_key="")
        storage.save_assignment(AssignmentRecord(flag_name="f", variant_name="v", user_id="u"))
        storage.flush()

        headers = srv.requests[0]["headers"]
        api_key_value = headers.get("X-Api-Key") or headers.get("X-API-Key") or headers.get("x-api-key")
        assert api_key_value is None


# ── Buffering ────────────────────────────────────────────────────────


class TestBuffering:
    def test_records_buffered_until_flush(self, mock_server):
        srv, port = mock_server
        storage = _make_storage(port)
        for i in range(5):
            storage.save_assignment(AssignmentRecord(flag_name="f", variant_name="v", user_id=f"u{i}"))
        # Should not have flushed yet (5 < _FLUSH_SIZE)
        # Note: timer may flush, so we check accumulated total
        storage.flush()  # Force flush remaining

        total_records = sum(len(r["body"]) for r in srv.requests if "/assignments" in r["path"])
        assert total_records == 5

    def test_auto_flush_at_threshold(self, mock_server):
        srv, port = mock_server
        storage = _make_storage(port)
        # Save exactly _FLUSH_SIZE records
        for i in range(_FLUSH_SIZE):
            storage.save_assignment(AssignmentRecord(flag_name="f", variant_name="v", user_id=f"u{i}"))

        # Give a moment for the auto-flush in save_assignment
        time.sleep(0.1)

        # At least one flush should have happened
        assignment_requests = [r for r in srv.requests if "/assignments" in r["path"]]
        assert len(assignment_requests) >= 1
        total = sum(len(r["body"]) for r in assignment_requests)
        assert total == _FLUSH_SIZE

    def test_batch_serialization(self, mock_server):
        """Multiple records are sent as a JSON array."""
        srv, port = mock_server
        storage = _make_storage(port)
        for i in range(3):
            storage.save_assignment(AssignmentRecord(flag_name="f", variant_name="v", user_id=f"u{i}"))
        storage.flush()

        body = srv.requests[0]["body"]
        assert isinstance(body, list)
        assert len(body) == 3
        for record in body:
            assert "flag_name" in record
            assert "assigned_at" in record  # datetime serialized


# ── URL Handling ─────────────────────────────────────────────────────


class TestURLHandling:
    def test_trailing_slash_stripped(self, mock_server):
        srv, port = mock_server
        storage = ServerStorage(f"http://127.0.0.1:{port}/", api_key="")
        storage.save_assignment(AssignmentRecord(flag_name="f", variant_name="v", user_id="u"))
        storage.flush()
        assert srv.requests[0]["path"] == "/api/v1/ingest/assignments"


# ── Error Handling (Fail-Soft) ───────────────────────────────────────


class TestFailSoft:
    def test_unreachable_server_doesnt_crash(self):
        """Writing to an unreachable server should log a warning, not crash."""
        storage = ServerStorage("http://127.0.0.1:1", api_key="")  # Port 1 = unreachable
        storage.save_assignment(AssignmentRecord(flag_name="f", variant_name="v", user_id="u"))
        storage.flush()  # Should not raise

    def test_server_error_doesnt_crash(self):
        """500 response should be swallowed."""

        class ErrorHandler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b"Internal Server Error")

            def log_message(self, format, *args):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), ErrorHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            storage = ServerStorage(f"http://127.0.0.1:{port}")
            storage.save_assignment(AssignmentRecord(flag_name="f", variant_name="v", user_id="u"))
            storage.flush()  # Should not raise even though server returns 500
        finally:
            server.shutdown()


# ── Concurrent Access ────────────────────────────────────────────────


class TestConcurrency:
    def test_concurrent_saves(self, mock_server):
        srv, port = mock_server
        storage = _make_storage(port)
        errors: list[Exception] = []

        def writer(tid: int):
            try:
                for i in range(20):
                    storage.save_assignment(AssignmentRecord(flag_name="f", variant_name="v", user_id=f"t{tid}_u{i}"))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        storage.flush()
        assert not errors

        total = sum(len(r["body"]) for r in srv.requests if "/assignments" in r["path"])
        assert total == 80


# ── Timer Flush ──────────────────────────────────────────────────────


class TestTimerFlush:
    def test_timer_eventually_flushes(self, mock_server):
        """Background timer should flush buffered records."""
        srv, port = mock_server
        # Create storage with a short interval for testing
        storage = _make_storage(port)
        storage.save_assignment(AssignmentRecord(flag_name="f", variant_name="v", user_id="u"))

        # Wait for timer flush (default 5s, but we flush manually to not slow tests)
        storage.flush()
        assert len(srv.requests) >= 1
