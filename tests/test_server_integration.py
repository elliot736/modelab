"""Integration tests for the full server stack (FastAPI + PostgreSQL via Docker).

These tests require Docker to be running. They spin up the docker-compose stack,
run tests against the live server, and tear it down.

Mark with pytest marker so they can be skipped when Docker is not available:
    pytest -m "not docker" to skip
    pytest -m docker to run only these
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import urllib.request
from datetime import datetime, timezone
from typing import Any

import pytest

import modelab

# Use the 'docker' marker — run with: pytest -m docker
# Skip by default with: pytest -m "not docker"
pytestmark = pytest.mark.docker

SERVER_URL = "http://localhost:8100"
COMPOSE_FILE = os.path.join(os.path.dirname(__file__), "..", "docker-compose.yml")


def _api(method: str, path: str, body: Any = None, api_key: str = "") -> dict:
    """Make an HTTP request to the server and return JSON response."""
    url = f"{SERVER_URL}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def _wait_for_server(timeout: int = 60) -> bool:
    """Wait until the server responds to health check requests."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            req = urllib.request.Request(f"{SERVER_URL}/api/v1/flags")
            with urllib.request.urlopen(req, timeout=3):
                return True
        except Exception:
            time.sleep(1)
    return False


@pytest.fixture(scope="module")
def server_stack():
    """Start docker-compose stack, wait for health, yield, then tear down."""
    # Start services
    subprocess.run(
        ["docker", "compose", "-f", COMPOSE_FILE, "up", "-d", "--build"],
        check=True,
        capture_output=True,
        timeout=180,
    )

    try:
        if not _wait_for_server():
            # Grab logs for debugging
            logs = subprocess.run(
                ["docker", "compose", "-f", COMPOSE_FILE, "logs"],
                capture_output=True,
                text=True,
            )
            pytest.fail(f"Server did not become healthy.\n{logs.stdout}\n{logs.stderr}")

        yield
    finally:
        subprocess.run(
            ["docker", "compose", "-f", COMPOSE_FILE, "down", "-v"],
            capture_output=True,
            timeout=60,
        )


@pytest.fixture(autouse=True)
def _reset_modelab():
    """Reset modelab global state between tests."""
    modelab.reset()
    yield
    modelab.reset()


# ── Ingest API Tests ─────────────────────────────────────────────────


class TestIngestAPI:
    def test_ingest_assignments(self, server_stack):
        now = datetime.now(timezone.utc).isoformat()
        records = [
            {
                "assignment_id": f"test-a-{i}",
                "flag_name": "test_flag",
                "variant_name": "control" if i < 5 else "treatment",
                "user_id": f"user_{i}",
                "session_id": "",
                "config_json": {"model": "gpt-4"},
                "assigned_at": now,
            }
            for i in range(10)
        ]
        result = _api("POST", "/api/v1/ingest/assignments", records)
        assert result["inserted"] == 10

    def test_ingest_executions(self, server_stack):
        now = datetime.now(timezone.utc).isoformat()
        records = [
            {
                "assignment_id": f"test-a-{i}",
                "latency_ms": 100.0 + i * 10,
                "input_tokens": 50,
                "output_tokens": 100,
                "cost": 0.01,
                "error": None,
                "metadata_json": {},
                "recorded_at": now,
            }
            for i in range(10)
        ]
        result = _api("POST", "/api/v1/ingest/executions", records)
        assert result["inserted"] == 10

    def test_ingest_events(self, server_stack):
        now = datetime.now(timezone.utc).isoformat()
        records = [
            {
                "event_id": f"test-e-{i}",
                "assignment_id": f"test-a-{i}",
                "event_type": "success",
                "event_name": "",
                "payload_json": {},
                "created_at": now,
            }
            for i in range(10)
        ]
        result = _api("POST", "/api/v1/ingest/events", records)
        assert result["inserted"] == 10

    def test_ingest_empty_batch(self, server_stack):
        result = _api("POST", "/api/v1/ingest/assignments", [])
        assert result["inserted"] == 0

    def test_ingest_duplicate_ignored(self, server_stack):
        """Duplicate assignment_id should not cause an error (ON CONFLICT DO NOTHING)."""
        now = datetime.now(timezone.utc).isoformat()
        record = {
            "assignment_id": "dup-test-1",
            "flag_name": "dup_flag",
            "variant_name": "v",
            "user_id": "u",
            "session_id": "",
            "config_json": {},
            "assigned_at": now,
        }
        _api("POST", "/api/v1/ingest/assignments", [record])
        result = _api("POST", "/api/v1/ingest/assignments", [record])
        assert result["inserted"] == 1  # Still reports count, but ON CONFLICT skips


# ── Dashboard API Tests ──────────────────────────────────────────────


class TestDashboardAPI:
    def test_list_flags(self, server_stack):
        result = _api("GET", "/api/v1/flags")
        assert isinstance(result, list)
        flag_names = {f["flag_name"] for f in result}
        assert "test_flag" in flag_names

    def test_list_flags_has_summary(self, server_stack):
        result = _api("GET", "/api/v1/flags")
        test_flag = next(f for f in result if f["flag_name"] == "test_flag")
        assert test_flag["total_assignments"] == 10
        assert set(test_flag["variants"]) == {"control", "treatment"}
        assert test_flag["success_rate"] is not None
        assert 0 <= test_flag["success_rate"] <= 1

    def test_get_flag_detail(self, server_stack):
        result = _api("GET", "/api/v1/flags/test_flag")
        assert result["flag_name"] == "test_flag"
        assert result["total_assignments"] == 10
        assert len(result["variants"]) == 2

        variant_names = {v["variant_name"] for v in result["variants"]}
        assert variant_names == {"control", "treatment"}

        for v in result["variants"]:
            assert v["assignments"] > 0
            assert v["success_count"] >= 0
            assert v["avg_latency_ms"] is not None

    def test_get_flag_detail_nonexistent(self, server_stack):
        result = _api("GET", "/api/v1/flags/nonexistent_flag")
        assert result["total_assignments"] == 0
        assert result["variants"] == []

    def test_get_timeline(self, server_stack):
        result = _api("GET", "/api/v1/flags/test_flag/timeline")
        assert isinstance(result, list)
        if result:  # May have data from the ingest tests
            assert "date" in result[0]
            assert "variant_name" in result[0]
            assert "assignments" in result[0]

    def test_get_timeline_nonexistent(self, server_stack):
        result = _api("GET", "/api/v1/flags/nonexistent_flag/timeline")
        assert result == []


# ── SDK → Server Integration ─────────────────────────────────────────


class TestSDKToServer:
    def test_server_storage_full_flow(self, server_stack):
        """Use the SDK's ServerStorage to send data, then verify via the API."""
        from modelab._server_storage import ServerStorage
        from modelab._types import AssignmentRecord, EventRecord, ExecutionRecord

        storage = ServerStorage(SERVER_URL)

        # Create assignments
        for i in range(5):
            storage.save_assignment(
                AssignmentRecord(
                    assignment_id=f"sdk-test-{i}",
                    flag_name="sdk_test_flag",
                    variant_name="v1" if i < 3 else "v2",
                    user_id=f"sdk_user_{i}",
                )
            )

        # Create executions
        for i in range(5):
            storage.save_execution(
                ExecutionRecord(
                    assignment_id=f"sdk-test-{i}",
                    latency_ms=50.0 + i * 10,
                    cost=0.005,
                )
            )

        # Create events
        for i in range(5):
            storage.save_event(
                EventRecord(
                    assignment_id=f"sdk-test-{i}",
                    event_type="success",
                )
            )

        # Flush everything
        storage.flush()

        # Give server a moment to process
        time.sleep(0.5)

        # Verify via dashboard API
        result = _api("GET", "/api/v1/flags/sdk_test_flag")
        assert result["total_assignments"] == 5
        assert len(result["variants"]) == 2

    def test_full_modelab_lifecycle_with_server(self, server_stack):
        """Full modelab.init → assign → record → evaluate lifecycle."""
        modelab.init(
            server=SERVER_URL,
            flags=[
                modelab.Flag(
                    name="e2e_test",
                    variants=[
                        modelab.Variant("control", weight=50, config={"model": "gpt-3.5"}),
                        modelab.Variant("treatment", weight=50, config={"model": "gpt-4"}),
                    ],
                    rollout_pct=100,
                ),
            ],
        )

        # Assign and track multiple users
        for i in range(10):
            ctx = modelab.EvalContext(user_id=f"e2e_user_{i}")
            assignment = modelab.assign("e2e_test", ctx)
            assert assignment is not None

            assignment.record(latency_ms=100.0, input_tokens=50, output_tokens=100, cost=0.01)

            assignment.mark_success()

        # evaluate() flushes and queries the server
        result = modelab.evaluate("e2e_test")
        assert result["total_assignments"] == 10
        total_success = sum(v["success_count"] for v in result["variants"])
        assert total_success == 10

    def test_evaluate_lifecycle(self, server_stack):
        """assign → record → mark_success → evaluate → verify metrics."""
        modelab.init(
            server=SERVER_URL,
            flags=[
                modelab.Flag(
                    name="eval_lifecycle",
                    variants=[
                        modelab.Variant("a", weight=50, config={"model": "gpt-4"}),
                        modelab.Variant("b", weight=50, config={"model": "gpt-3.5"}),
                    ],
                    rollout_pct=100,
                ),
            ],
        )

        for i in range(20):
            ctx = modelab.EvalContext(user_id=f"eval_user_{i}")
            assignment = modelab.assign("eval_lifecycle", ctx)
            assert assignment is not None

            assignment.record(latency_ms=80.0, input_tokens=30, output_tokens=60, cost=0.005)

            if i % 3 == 0:
                assignment.mark_failure()
            else:
                assignment.mark_success()

        result = modelab.evaluate("eval_lifecycle")
        assert result["total_assignments"] == 20
        assert len(result["variants"]) == 2

        total_success = sum(v["success_count"] for v in result["variants"])
        total_failure = sum(v["failure_count"] for v in result["variants"])
        assert total_success + total_failure == 20

    def test_evaluate_nonexistent_flag(self, server_stack):
        """evaluate() on a registered but empty flag returns empty results from server."""
        modelab.init(
            server=SERVER_URL,
            flags=[
                modelab.Flag(
                    name="empty_eval_flag",
                    variants=[modelab.Variant("v")],
                ),
            ],
        )
        result = modelab.evaluate("empty_eval_flag")
        assert result["total_assignments"] == 0
        assert result["variants"] == []

    def test_evaluate_unregistered_flag_raises(self, server_stack):
        """evaluate() on a flag not registered in init() raises FlagNotFoundError."""
        modelab.init(
            server=SERVER_URL,
            flags=[modelab.Flag(name="registered", variants=[modelab.Variant("v")])],
        )
        with pytest.raises(modelab._errors.FlagNotFoundError):
            modelab.evaluate("not_registered")


# ── Concurrent SDK → Server ──────────────────────────────────────────


class TestConcurrentSDK:
    def test_concurrent_assigns_to_server(self, server_stack):
        """Multiple threads assigning concurrently against the live server."""
        modelab.init(
            server=SERVER_URL,
            flags=[
                modelab.Flag(
                    name="concurrent_server",
                    variants=[
                        modelab.Variant("a", weight=50),
                        modelab.Variant("b", weight=50),
                    ],
                    rollout_pct=100,
                ),
            ],
        )
        errors: list[Exception] = []

        def worker(thread_id: int):
            try:
                for i in range(20):
                    ctx = modelab.EvalContext(user_id=f"t{thread_id}_u{i}")
                    a = modelab.assign("concurrent_server", ctx)
                    if a:
                        a.record(latency_ms=50.0, cost=0.01)
                        a.mark_success()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors

        result = modelab.evaluate("concurrent_server")
        assert result["total_assignments"] == 80


# ── API Key Authentication ───────────────────────────────────────────


class TestAPIKeyAuth:
    """These tests only work when MODELAB_API_KEY is set in docker-compose."""

    def test_ingest_without_key_works_when_no_key_set(self, server_stack):
        """When API key is empty (default), ingest should work without a key."""
        now = datetime.now(timezone.utc).isoformat()
        record = {
            "assignment_id": "auth-test-1",
            "flag_name": "auth_flag",
            "variant_name": "v",
            "user_id": "u",
            "session_id": "",
            "config_json": {},
            "assigned_at": now,
        }
        result = _api("POST", "/api/v1/ingest/assignments", [record])
        assert result["inserted"] == 1
