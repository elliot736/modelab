"""Tests for _types module — dataclass behavior, defaults, and frozen semantics."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from modelab._types import (
    AssignmentRecord,
    EvalContext,
    EventRecord,
    ExecutionRecord,
    Flag,
    Variant,
)


# ── TestVariant ──────────────────────────────────────────────────────


class TestVariant:
    def test_defaults(self):
        v = Variant(name="v")
        assert v.name == "v"
        assert v.weight == 50
        assert v.config == {}

    def test_with_config(self):
        v = Variant(name="v", weight=70, config={"model": "gpt-4"})
        assert v.weight == 70
        assert v.config["model"] == "gpt-4"

    def test_frozen(self):
        v = Variant(name="v")
        with pytest.raises(AttributeError):
            v.name = "changed"  # type: ignore[misc]

    def test_equality(self):
        v1 = Variant(name="v", weight=50, config={"a": 1})
        v2 = Variant(name="v", weight=50, config={"a": 1})
        assert v1 == v2

    def test_inequality(self):
        v1 = Variant(name="a")
        v2 = Variant(name="b")
        assert v1 != v2


# ── TestFlag ─────────────────────────────────────────────────────────


class TestFlag:
    def test_defaults(self):
        f = Flag(name="f")
        assert f.name == "f"
        assert f.variants == []
        assert f.rollout_pct == 100.0

    def test_with_variants(self):
        f = Flag(name="f", variants=[Variant("a"), Variant("b")], rollout_pct=50)
        assert len(f.variants) == 2
        assert f.rollout_pct == 50

    def test_frozen(self):
        f = Flag(name="f")
        with pytest.raises(AttributeError):
            f.name = "changed"  # type: ignore[misc]


# ── TestEvalContext ──────────────────────────────────────────────────


class TestEvalContext:
    def test_defaults(self):
        ctx = EvalContext(user_id="u1")
        assert ctx.user_id == "u1"
        assert ctx.session_id == ""

    def test_with_session(self):
        ctx = EvalContext(user_id="u1", session_id="s1")
        assert ctx.session_id == "s1"

    def test_frozen(self):
        ctx = EvalContext(user_id="u1")
        with pytest.raises(AttributeError):
            ctx.user_id = "changed"  # type: ignore[misc]

    def test_equality(self):
        c1 = EvalContext(user_id="u1", session_id="s1")
        c2 = EvalContext(user_id="u1", session_id="s1")
        assert c1 == c2


# ── TestAssignmentRecord ─────────────────────────────────────────────


class TestAssignmentRecord:
    def test_auto_uuid(self):
        r1 = AssignmentRecord()
        r2 = AssignmentRecord()
        assert r1.assignment_id != r2.assignment_id
        uuid.UUID(r1.assignment_id)  # Should not raise

    def test_auto_timestamp(self):
        r = AssignmentRecord()
        assert isinstance(r.assigned_at, datetime)
        assert r.assigned_at.tzinfo is not None

    def test_defaults(self):
        r = AssignmentRecord()
        assert r.flag_name == ""
        assert r.variant_name == ""
        assert r.user_id == ""
        assert r.session_id == ""
        assert r.config_json == {}

    def test_mutable(self):
        """AssignmentRecord is not frozen — fields can be modified."""
        r = AssignmentRecord()
        r.flag_name = "test"
        assert r.flag_name == "test"

    def test_config_json_independent(self):
        """Default config_json should be independent between instances."""
        r1 = AssignmentRecord()
        r2 = AssignmentRecord()
        r1.config_json["key"] = "value"
        assert "key" not in r2.config_json


# ── TestExecutionRecord ──────────────────────────────────────────────


class TestExecutionRecord:
    def test_defaults(self):
        r = ExecutionRecord()
        assert r.assignment_id == ""
        assert r.latency_ms is None
        assert r.input_tokens is None
        assert r.output_tokens is None
        assert r.cost is None
        assert r.error is None
        assert r.metadata_json == {}

    def test_auto_timestamp(self):
        r = ExecutionRecord()
        assert isinstance(r.recorded_at, datetime)


# ── TestEventRecord ──────────────────────────────────────────────────


class TestEventRecord:
    def test_auto_uuid(self):
        r = EventRecord()
        uuid.UUID(r.event_id)  # Should not raise

    def test_defaults(self):
        r = EventRecord()
        assert r.assignment_id == ""
        assert r.event_type == ""
        assert r.event_name == ""
        assert r.payload_json == {}

    def test_payload_independent(self):
        r1 = EventRecord()
        r2 = EventRecord()
        r1.payload_json["key"] = "value"
        assert "key" not in r2.payload_json
