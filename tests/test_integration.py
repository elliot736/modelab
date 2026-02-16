"""End-to-end integration tests for the public API — using a mock ingest server."""

from __future__ import annotations

import http.server
import json
import threading

import pytest

import modelab
from modelab._errors import (
    FlagNotFoundError,
    InvalidFlagError,
    ModelabError,
    NotInitializedError,
)
from modelab._types import EvalContext, Flag, Variant


# ── Mock Ingest Server ───────────────────────────────────────────────


class _MockIngestServer:
    """Minimal HTTP server that accepts POST ingest requests and returns 200."""

    def __init__(self) -> None:
        self._server: http.server.HTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> int:
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                self.rfile.read(length)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"inserted": 1}')

            def log_message(self, format, *args):
                pass

        self._server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return port

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()


@pytest.fixture(scope="module")
def mock_server():
    """Start a mock HTTP server that accepts ingest requests."""
    srv = _MockIngestServer()
    port = srv.start()
    yield port
    srv.stop()


@pytest.fixture(autouse=True)
def _reset():
    """Reset modelab state between tests."""
    modelab.reset()
    yield
    modelab.reset()


# ── Initialization ───────────────────────────────────────────────────


class TestInit:
    def test_not_initialized_assign(self):
        with pytest.raises(NotInitializedError):
            modelab.assign("flag", EvalContext(user_id="u"))

    def test_not_initialized_evaluate(self):
        with pytest.raises(NotInitializedError):
            modelab.evaluate("flag")

    def test_init_with_server(self, mock_server):
        modelab.init(
            server=f"http://127.0.0.1:{mock_server}",
            flags=[Flag(name="f", variants=[Variant("v")])],
        )
        a = modelab.assign("f", EvalContext(user_id="u"))
        assert a is not None

    def test_init_empty_flags(self, mock_server):
        """init() with no flags is valid — assign will raise FlagNotFoundError."""
        modelab.init(server=f"http://127.0.0.1:{mock_server}", flags=[])
        with pytest.raises(FlagNotFoundError):
            modelab.assign("anything", EvalContext(user_id="u"))

    def test_init_multiple_flags(self, mock_server):
        modelab.init(
            server=f"http://127.0.0.1:{mock_server}",
            flags=[
                Flag(name="f1", variants=[Variant("a")]),
                Flag(name="f2", variants=[Variant("b")]),
                Flag(name="f3", variants=[Variant("c")]),
            ],
        )
        assert modelab.assign("f1", EvalContext(user_id="u")) is not None
        assert modelab.assign("f2", EvalContext(user_id="u")) is not None
        assert modelab.assign("f3", EvalContext(user_id="u")) is not None

    def test_reinit_overwrites_state(self, mock_server):
        """Second init() replaces all flags and storage."""
        url = f"http://127.0.0.1:{mock_server}"
        modelab.init(server=url, flags=[Flag(name="f1", variants=[Variant("a")])])
        modelab.init(server=url, flags=[Flag(name="f2", variants=[Variant("b")])])
        with pytest.raises(FlagNotFoundError):
            modelab.assign("f1", EvalContext(user_id="u"))
        assert modelab.assign("f2", EvalContext(user_id="u")) is not None

    def test_reset_clears_state(self, mock_server):
        modelab.init(
            server=f"http://127.0.0.1:{mock_server}",
            flags=[Flag(name="f", variants=[Variant("v")])],
        )
        modelab.reset()
        with pytest.raises(NotInitializedError):
            modelab.assign("f", EvalContext(user_id="u"))


# ── Flag Validation ──────────────────────────────────────────────────


class TestFlagValidation:
    def test_flag_no_variants(self, mock_server):
        with pytest.raises(InvalidFlagError):
            modelab.init(
                server=f"http://127.0.0.1:{mock_server}",
                flags=[Flag(name="empty", variants=[])],
            )

    def test_flag_rollout_negative(self, mock_server):
        with pytest.raises(InvalidFlagError):
            modelab.init(
                server=f"http://127.0.0.1:{mock_server}",
                flags=[Flag(name="neg", variants=[Variant("v")], rollout_pct=-1)],
            )

    def test_flag_rollout_over_100(self, mock_server):
        with pytest.raises(InvalidFlagError):
            modelab.init(
                server=f"http://127.0.0.1:{mock_server}",
                flags=[Flag(name="big", variants=[Variant("v")], rollout_pct=101)],
            )

    def test_flag_rollout_boundary_0(self, mock_server):
        modelab.init(
            server=f"http://127.0.0.1:{mock_server}",
            flags=[Flag(name="f", variants=[Variant("v")], rollout_pct=0)],
        )
        assert modelab.assign("f", EvalContext(user_id="u")) is None

    def test_flag_rollout_boundary_100(self, mock_server):
        modelab.init(
            server=f"http://127.0.0.1:{mock_server}",
            flags=[Flag(name="f", variants=[Variant("v")], rollout_pct=100)],
        )
        assert modelab.assign("f", EvalContext(user_id="u")) is not None

    def test_invalid_flag_error_is_modelab_error(self, mock_server):
        """InvalidFlagError inherits from ModelabError."""
        with pytest.raises(ModelabError):
            modelab.init(
                server=f"http://127.0.0.1:{mock_server}",
                flags=[Flag(name="bad", variants=[])],
            )


# ── Assignment ───────────────────────────────────────────────────────


class TestAssignment:
    def test_flag_not_found(self, mock_server):
        modelab.init(
            server=f"http://127.0.0.1:{mock_server}",
            flags=[Flag(name="a", variants=[Variant("v")])],
        )
        with pytest.raises(FlagNotFoundError) as exc_info:
            modelab.assign("nonexistent", EvalContext(user_id="u"))
        assert exc_info.value.name == "nonexistent"

    def test_deterministic(self, mock_server):
        modelab.init(
            server=f"http://127.0.0.1:{mock_server}",
            flags=[
                Flag(name="det", variants=[Variant("a", weight=50), Variant("b", weight=50)], rollout_pct=100)
            ],
        )
        ctx = EvalContext(user_id="stable_user")
        a1 = modelab.assign("det", ctx)
        a2 = modelab.assign("det", ctx)
        assert a1 is not None and a2 is not None
        assert a1.variant_name == a2.variant_name

    def test_rollout_zero(self, mock_server):
        modelab.init(
            server=f"http://127.0.0.1:{mock_server}",
            flags=[Flag(name="off", variants=[Variant("v")], rollout_pct=0)],
        )
        assert modelab.assign("off", EvalContext(user_id="u")) is None

    def test_assignment_has_correct_properties(self, mock_server):
        modelab.init(
            server=f"http://127.0.0.1:{mock_server}",
            flags=[Flag(name="f", variants=[Variant("v", config={"model": "gpt-4"})])],
        )
        a = modelab.assign("f", EvalContext(user_id="user_1", session_id="sess_1"))
        assert a is not None
        assert a.flag_name == "f"
        assert a.variant_name == "v"
        assert a.config == {"model": "gpt-4"}
        assert a.context.user_id == "user_1"
        assert a.context.session_id == "sess_1"
        assert len(a.assignment_id) > 0

    def test_different_users_can_get_different_variants(self, mock_server):
        modelab.init(
            server=f"http://127.0.0.1:{mock_server}",
            flags=[
                Flag(
                    name="ab",
                    variants=[Variant("a", weight=50), Variant("b", weight=50)],
                    rollout_pct=100,
                )
            ],
        )
        variants_seen = set()
        for i in range(200):
            a = modelab.assign("ab", EvalContext(user_id=f"user_{i}"))
            variants_seen.add(a.variant_name)
        assert variants_seen == {"a", "b"}


# ── Concurrent Usage ─────────────────────────────────────────────────


class TestConcurrency:
    def test_concurrent_assigns(self, mock_server):
        """Multiple threads assigning concurrently should not crash."""
        modelab.init(
            server=f"http://127.0.0.1:{mock_server}",
            flags=[
                Flag(
                    name="concurrent",
                    variants=[Variant("a", weight=50), Variant("b", weight=50)],
                    rollout_pct=100,
                )
            ],
        )
        errors: list[Exception] = []
        results: list[str] = []

        def assign_many(start: int):
            try:
                for i in range(100):
                    a = modelab.assign("concurrent", EvalContext(user_id=f"u{start}_{i}"))
                    if a:
                        results.append(a.variant_name)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=assign_many, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(results) == 400
