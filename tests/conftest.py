"""Shared fixtures for modelab tests."""

from __future__ import annotations

import pytest

from modelab._types import EvalContext, Flag, Variant


@pytest.fixture
def simple_flag() -> Flag:
    """A two-variant 50/50 A/B test flag with 100% rollout."""
    return Flag(
        name="test_flag",
        variants=[
            Variant("control", weight=50, config={"model": "gpt-3.5"}),
            Variant("treatment", weight=50, config={"model": "gpt-4"}),
        ],
        rollout_pct=100,
    )


@pytest.fixture
def ctx() -> EvalContext:
    """An evaluation context with both user_id and session_id populated."""
    return EvalContext(user_id="user_123", session_id="sess_abc")
