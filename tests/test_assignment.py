"""Tests for the Assignment class — record(), events, duck-typing, and error handling."""

from __future__ import annotations

import threading

import pytest

from modelab._assignment import Assignment, _extract_usage_from_response
from modelab._types import AssignmentRecord, EvalContext, EventRecord, ExecutionRecord


class FakeStorage:
    """In-memory storage for unit tests (replaces SQLiteStorage)."""

    def __init__(self) -> None:
        self.executions: list[ExecutionRecord] = []
        self.events: list[EventRecord] = []

    def save_assignment(self, record: AssignmentRecord) -> None:
        pass  # Not needed for assignment-level tests

    def save_execution(self, record: ExecutionRecord) -> None:
        self.executions.append(record)

    def save_event(self, record: EventRecord) -> None:
        self.events.append(record)

    def flush(self) -> None:
        pass


@pytest.fixture
def storage() -> FakeStorage:
    """In-memory fake storage for testing."""
    return FakeStorage()


def _make_assignment_obj(
    storage: FakeStorage,
    flag: str = "test_flag",
    variant: str = "control",
    aid: str = "asgn-001",
) -> Assignment:
    """Create an Assignment instance wired to FakeStorage."""
    return Assignment(
        flag_name=flag,
        variant_name=variant,
        config={"model": "gpt-4"},
        context=EvalContext(user_id="u1"),
        storage=storage,
        assignment_id=aid,
    )


# ── Properties ───────────────────────────────────────────────────────


class TestProperties:
    def test_all_properties(self, storage: FakeStorage):
        a = _make_assignment_obj(storage)
        assert a.flag_name == "test_flag"
        assert a.variant_name == "control"
        assert a.config == {"model": "gpt-4"}
        assert a.context.user_id == "u1"
        assert a.assignment_id == "asgn-001"

    def test_config_returns_same_reference(self, storage: FakeStorage):
        """Config property returns the internal dict (not a copy)."""
        a = _make_assignment_obj(storage)
        cfg = a.config
        assert cfg is a.config  # Same reference for performance


# ── Manual Record ────────────────────────────────────────────────────


class TestRecord:
    def test_record_all_fields(self, storage: FakeStorage):
        a = _make_assignment_obj(storage)
        a.record(
            latency_ms=200.0,
            input_tokens=50,
            output_tokens=100,
            cost=0.02,
            error="some error",
            provider="openai",
        )
        ex = storage.executions[0]
        assert ex.latency_ms == 200.0
        assert ex.input_tokens == 50
        assert ex.output_tokens == 100
        assert ex.cost == 0.02
        assert ex.error == "some error"
        assert ex.metadata_json == {"provider": "openai"}

    def test_record_minimal(self, storage: FakeStorage):
        a = _make_assignment_obj(storage)
        a.record()
        ex = storage.executions[0]
        assert ex.latency_ms is None
        assert ex.cost is None

    def test_record_replaces_previous(self, storage: FakeStorage):
        """Multiple record() calls append both records (no SQLite dedup)."""
        a = _make_assignment_obj(storage)
        a.record(latency_ms=100.0)
        a.record(latency_ms=200.0)
        assert len(storage.executions) == 2
        assert storage.executions[0].latency_ms == 100.0
        assert storage.executions[1].latency_ms == 200.0

    def test_record_openai_response(self, storage: FakeStorage):
        """Duck-type OpenAI response: usage.prompt_tokens / completion_tokens."""
        a = _make_assignment_obj(storage)

        class Usage:
            prompt_tokens = 42
            completion_tokens = 108

        class Response:
            usage = Usage()

        a.record(Response(), cost=0.01)
        ex = storage.executions[0]
        assert ex.input_tokens == 42
        assert ex.output_tokens == 108
        assert ex.cost == 0.01

    def test_record_anthropic_response(self, storage: FakeStorage):
        """Duck-type Anthropic response: usage.input_tokens / output_tokens."""
        a = _make_assignment_obj(storage)

        class Usage:
            input_tokens = 55
            output_tokens = 200

        class Response:
            usage = Usage()

        a.record(Response())
        ex = storage.executions[0]
        assert ex.input_tokens == 55
        assert ex.output_tokens == 200

    def test_record_kwargs_override_extracted(self, storage: FakeStorage):
        """Explicit kwargs always override duck-typed values."""
        a = _make_assignment_obj(storage)

        class Usage:
            prompt_tokens = 42
            completion_tokens = 108

        class Response:
            usage = Usage()

        a.record(Response(), input_tokens=99, output_tokens=999)
        ex = storage.executions[0]
        assert ex.input_tokens == 99
        assert ex.output_tokens == 999

    def test_record_response_no_usage_attr(self, storage: FakeStorage):
        """Response object with no .usage attribute — tokens stay None."""
        a = _make_assignment_obj(storage)

        class Response:
            pass

        a.record(Response(), cost=0.05)
        ex = storage.executions[0]
        assert ex.input_tokens is None
        assert ex.output_tokens is None
        assert ex.cost == 0.05

    def test_record_response_usage_is_none(self, storage: FakeStorage):
        """Response object where usage=None — tokens stay None."""
        a = _make_assignment_obj(storage)

        class Response:
            usage = None

        a.record(Response())
        ex = storage.executions[0]
        assert ex.input_tokens is None
        assert ex.output_tokens is None

    def test_record_response_with_metadata(self, storage: FakeStorage):
        """Response + extra metadata kwargs."""
        a = _make_assignment_obj(storage)

        class Usage:
            prompt_tokens = 10
            completion_tokens = 20

        class Response:
            usage = Usage()

        a.record(Response(), model="gpt-4o", region="us-east-1")
        ex = storage.executions[0]
        assert ex.input_tokens == 10
        assert ex.output_tokens == 20
        assert ex.metadata_json == {"model": "gpt-4o", "region": "us-east-1"}

    def test_record_response_with_error(self, storage: FakeStorage):
        """Response + error string."""
        a = _make_assignment_obj(storage)

        class Usage:
            prompt_tokens = 5
            completion_tokens = 0

        class Response:
            usage = Usage()

        a.record(Response(), error="timeout")
        ex = storage.executions[0]
        assert ex.input_tokens == 5
        assert ex.output_tokens == 0
        assert ex.error == "timeout"


# ── Extract usage helper ─────────────────────────────────────────────


class TestExtractUsage:
    def test_openai_style(self):
        class Usage:
            prompt_tokens = 10
            completion_tokens = 20

        class Resp:
            usage = Usage()

        assert _extract_usage_from_response(Resp()) == (10, 20)

    def test_anthropic_style(self):
        class Usage:
            input_tokens = 30
            output_tokens = 40

        class Resp:
            usage = Usage()

        assert _extract_usage_from_response(Resp()) == (30, 40)

    def test_no_usage_attr(self):
        class Resp:
            pass

        assert _extract_usage_from_response(Resp()) == (None, None)

    def test_usage_is_none(self):
        class Resp:
            usage = None

        assert _extract_usage_from_response(Resp()) == (None, None)

    def test_plain_string(self):
        assert _extract_usage_from_response("hello") == (None, None)

    def test_dict_response(self):
        assert _extract_usage_from_response({"usage": {"tokens": 5}}) == (None, None)


# ── Events ───────────────────────────────────────────────────────────


class TestEvents:
    def test_mark_success(self, storage: FakeStorage):
        a = _make_assignment_obj(storage)
        a.mark_success()
        assert len(storage.events) == 1
        assert storage.events[0].event_type == "success"
        assert storage.events[0].event_name == ""
        assert storage.events[0].payload_json == {}

    def test_mark_success_with_payload(self, storage: FakeStorage):
        a = _make_assignment_obj(storage)
        a.mark_success({"score": 0.95})
        assert storage.events[0].payload_json == {"score": 0.95}

    def test_mark_failure(self, storage: FakeStorage):
        a = _make_assignment_obj(storage)
        a.mark_failure({"reason": "timeout"})
        ev = storage.events[0]
        assert ev.event_type == "failure"
        assert ev.payload_json == {"reason": "timeout"}

    def test_mark_failure_no_payload(self, storage: FakeStorage):
        a = _make_assignment_obj(storage)
        a.mark_failure()
        assert storage.events[0].payload_json == {}

    def test_mark_custom_event(self, storage: FakeStorage):
        a = _make_assignment_obj(storage)
        a.mark_custom_event("copied")
        ev = storage.events[0]
        assert ev.event_type == "custom"
        assert ev.event_name == "copied"

    def test_mark_custom_event_with_payload(self, storage: FakeStorage):
        a = _make_assignment_obj(storage)
        a.mark_custom_event("feedback", {"rating": 5, "comment": "good"})
        ev = storage.events[0]
        assert ev.payload_json == {"rating": 5, "comment": "good"}

    def test_multiple_events(self, storage: FakeStorage):
        """Multiple events on the same assignment create multiple records."""
        a = _make_assignment_obj(storage)
        a.mark_success()
        a.mark_custom_event("copied")
        a.mark_custom_event("shared")
        assert len(storage.events) == 3

    def test_both_success_and_failure(self, storage: FakeStorage):
        a = _make_assignment_obj(storage)
        a.mark_success()
        a.mark_failure()
        types = {e.event_type for e in storage.events}
        assert types == {"success", "failure"}

    def test_custom_event_special_name(self, storage: FakeStorage):
        a = _make_assignment_obj(storage)
        a.mark_custom_event("user:thumbs_up:v2")
        assert storage.events[0].event_name == "user:thumbs_up:v2"


# ── Fail-Soft Behavior ──────────────────────────────────────────────


class TestFailSoft:
    def _broken_assignment(self) -> Assignment:
        class BrokenStorage:
            def save_execution(self, r):
                raise RuntimeError("db down")

            def save_event(self, r):
                raise RuntimeError("db down")

        return Assignment(
            flag_name="f",
            variant_name="v",
            config={},
            context=EvalContext(user_id="u"),
            storage=BrokenStorage(),  # type: ignore[arg-type]
            assignment_id="x",
        )

    def test_record_swallows_errors(self):
        a = self._broken_assignment()
        a.record(latency_ms=1.0)  # Should not raise

    def test_mark_success_swallows_errors(self):
        a = self._broken_assignment()
        a.mark_success()

    def test_mark_failure_swallows_errors(self):
        a = self._broken_assignment()
        a.mark_failure()

    def test_mark_custom_event_swallows_errors(self):
        a = self._broken_assignment()
        a.mark_custom_event("test")


# ── Concurrent Access ────────────────────────────────────────────────


class TestConcurrency:
    def test_concurrent_events(self, storage: FakeStorage):
        """Multiple threads marking events on different assignments."""
        errors: list[Exception] = []

        def mark_events(start: int):
            try:
                for i in range(start, start + 10):
                    a = Assignment(
                        flag_name="test_flag",
                        variant_name="v",
                        config={},
                        context=EvalContext(user_id=f"u{i}"),
                        storage=storage,
                        assignment_id=f"a{i}",
                    )
                    a.mark_success()
                    a.mark_custom_event("test")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=mark_events, args=(i * 10,)) for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(storage.events) == 40  # 20 assignments x 2 events each
