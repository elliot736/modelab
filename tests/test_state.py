"""Tests for the _state module — singleton configuration and validation."""

from __future__ import annotations

import pytest

from modelab._errors import InvalidFlagError
from modelab._server_storage import ServerStorage
from modelab._state import _State
from modelab._types import Flag, Variant


@pytest.fixture
def state() -> _State:
    """Fresh _State instance for each test."""
    return _State()


@pytest.fixture
def storage() -> ServerStorage:
    """Mock ServerStorage for testing."""
    return ServerStorage("http://localhost:9999")


# ── TestConfigure ────────────────────────────────────────────────────


class TestConfigure:
    def test_basic_configure(self, state: _State, storage: ServerStorage):
        state.configure(storage, [Flag(name="f", variants=[Variant("v")])])
        assert state.initialized
        assert "f" in state.flags

    def test_multiple_flags(self, state: _State, storage: ServerStorage):
        state.configure(
            storage,
            [
                Flag(name="f1", variants=[Variant("a")]),
                Flag(name="f2", variants=[Variant("b")]),
            ],
        )
        assert len(state.flags) == 2

    def test_empty_flags_list(self, state: _State, storage: ServerStorage):
        state.configure(storage, [])
        assert state.initialized
        assert state.flags == {}

    def test_duplicate_flag_names_last_wins(self, state: _State, storage: ServerStorage):
        state.configure(
            storage,
            [
                Flag(name="f", variants=[Variant("a")]),
                Flag(name="f", variants=[Variant("b")]),
            ],
        )
        assert state.flags["f"].variants[0].name == "b"

    def test_reconfigure_overwrites(self, state: _State, storage: ServerStorage):
        state.configure(storage, [Flag(name="f1", variants=[Variant("v")])])
        state.configure(storage, [Flag(name="f2", variants=[Variant("v")])])
        assert "f1" not in state.flags
        assert "f2" in state.flags


# ── TestValidation ───────────────────────────────────────────────────


class TestValidation:
    def test_reject_flag_with_no_variants(self, state: _State, storage: ServerStorage):
        with pytest.raises(InvalidFlagError, match="no variants"):
            state.configure(storage, [Flag(name="empty", variants=[])])

    def test_reject_negative_rollout(self, state: _State, storage: ServerStorage):
        with pytest.raises(InvalidFlagError, match="rollout_pct"):
            state.configure(
                storage, [Flag(name="neg", variants=[Variant("v")], rollout_pct=-0.1)]
            )

    def test_reject_rollout_over_100(self, state: _State, storage: ServerStorage):
        with pytest.raises(InvalidFlagError, match="rollout_pct"):
            state.configure(
                storage, [Flag(name="big", variants=[Variant("v")], rollout_pct=100.1)]
            )

    def test_accept_rollout_0(self, state: _State, storage: ServerStorage):
        state.configure(storage, [Flag(name="f", variants=[Variant("v")], rollout_pct=0)])
        assert state.initialized

    def test_accept_rollout_100(self, state: _State, storage: ServerStorage):
        state.configure(storage, [Flag(name="f", variants=[Variant("v")], rollout_pct=100)])
        assert state.initialized

    def test_accept_fractional_rollout(self, state: _State, storage: ServerStorage):
        state.configure(
            storage, [Flag(name="f", variants=[Variant("v")], rollout_pct=33.33)]
        )
        assert state.initialized

    def test_validation_fails_before_state_changes(self, state: _State, storage: ServerStorage):
        """If validation fails, state should remain unchanged."""
        state.configure(storage, [Flag(name="good", variants=[Variant("v")])])
        with pytest.raises(InvalidFlagError):
            state.configure(storage, [Flag(name="bad", variants=[])])
        # State should still have the previous valid config
        assert "good" in state.flags


# ── TestReset ────────────────────────────────────────────────────────


class TestReset:
    def test_reset(self, state: _State, storage: ServerStorage):
        state.configure(storage, [Flag(name="f", variants=[Variant("v")])])
        state.reset()
        assert not state.initialized
        assert state.storage is None
        assert state.flags == {}

    def test_reset_before_configure(self, state: _State):
        state.reset()  # Should not raise
        assert not state.initialized


# ── TestInitialized ──────────────────────────────────────────────────


class TestInitialized:
    def test_not_initialized_by_default(self, state: _State):
        assert not state.initialized

    def test_initialized_after_configure(self, state: _State, storage: ServerStorage):
        state.configure(storage, [Flag(name="f", variants=[Variant("v")])])
        assert state.initialized

    def test_not_initialized_after_reset(self, state: _State, storage: ServerStorage):
        state.configure(storage, [Flag(name="f", variants=[Variant("v")])])
        state.reset()
        assert not state.initialized
