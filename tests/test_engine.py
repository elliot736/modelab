"""Tests for the assignment engine — comprehensive edge cases and boundary conditions."""

from __future__ import annotations

import statistics

from modelab._engine import BUCKET_COUNT, _bucket, assign_variant
from modelab._types import EvalContext, Flag, Variant


# ── Bucketing ────────────────────────────────────────────────────────


class TestBucket:
    def test_deterministic(self):
        """Same inputs always produce the same bucket."""
        assert _bucket("flag", "user1") == _bucket("flag", "user1")

    def test_range(self):
        """Buckets are within [0, BUCKET_COUNT)."""
        for i in range(500):
            b = _bucket("flag", f"user_{i}")
            assert 0 <= b < BUCKET_COUNT

    def test_distribution_mean(self):
        """Mean bucket value is close to BUCKET_COUNT/2."""
        n = 10_000
        buckets = [_bucket("flag", f"u{i}") for i in range(n)]
        mean = sum(buckets) / n
        expected = BUCKET_COUNT / 2
        assert abs(mean - expected) < BUCKET_COUNT * 0.03

    def test_distribution_variance(self):
        """Variance indicates uniform spread, not clustering."""
        n = 5_000
        buckets = [_bucket("flag", f"u{i}") for i in range(n)]
        stddev = statistics.stdev(buckets)
        # For uniform [0, 10000), expected stddev ≈ 2886
        assert 2500 < stddev < 3300

    def test_different_flags_different_buckets(self):
        """Different flag names produce different buckets for the same user."""
        b1 = _bucket("flag_a", "user1")
        b2 = _bucket("flag_b", "user1")
        # Not guaranteed to differ for a single pair, but for many pairs most will differ
        different = sum(
            1 for i in range(200)
            if _bucket("flagA", f"u{i}") != _bucket("flagB", f"u{i}")
        )
        assert different > 150  # Most should differ

    def test_empty_user_id(self):
        """Empty string user_id is valid and deterministic."""
        b1 = _bucket("flag", "")
        b2 = _bucket("flag", "")
        assert b1 == b2
        assert 0 <= b1 < BUCKET_COUNT

    def test_special_characters(self):
        """User IDs with special characters produce valid buckets."""
        for uid in ["user@example.com", "user:with:colons", "émojis🎉", "日本語", "a" * 10_000]:
            b = _bucket("flag", uid)
            assert 0 <= b < BUCKET_COUNT

    def test_unicode_flag_name(self):
        b = _bucket("实验_flag", "user1")
        assert 0 <= b < BUCKET_COUNT

    def test_collision_rate(self):
        """Bucket collision rate for different users should be ~1/BUCKET_COUNT."""
        n = 1_000
        buckets = [_bucket("flag", f"u{i}") for i in range(n)]
        unique = len(set(buckets))
        # With 1000 draws from 10000 buckets, expect ~950+ unique (birthday problem)
        assert unique > 900


# ── Rollout Gate ─────────────────────────────────────────────────────


class TestRollout:
    def test_zero_rollout_always_none(self):
        """0% rollout → every user gets None."""
        flag = Flag(name="off", variants=[Variant("a", weight=100)], rollout_pct=0)
        for i in range(200):
            assert assign_variant(flag, EvalContext(user_id=f"u{i}")) is None

    def test_full_rollout_never_none(self):
        """100% rollout → no user gets None."""
        flag = Flag(name="on", variants=[Variant("a", weight=100)], rollout_pct=100)
        for i in range(200):
            assert assign_variant(flag, EvalContext(user_id=f"u{i}")) is not None

    def test_50_percent_rollout(self):
        """50% rollout → roughly half assigned."""
        flag = Flag(name="half", variants=[Variant("a", weight=100)], rollout_pct=50)
        assigned = sum(
            1 for i in range(2000)
            if assign_variant(flag, EvalContext(user_id=f"u{i}")) is not None
        )
        assert 850 < assigned < 1150  # ~1000 ± 150

    def test_1_percent_rollout(self):
        """1% rollout → ~1% of users assigned."""
        flag = Flag(name="tiny", variants=[Variant("a", weight=100)], rollout_pct=1)
        assigned = sum(
            1 for i in range(10_000)
            if assign_variant(flag, EvalContext(user_id=f"u{i}")) is not None
        )
        assert 50 < assigned < 200  # ~100 ± broad tolerance

    def test_99_percent_rollout(self):
        """99% rollout → most users assigned, some excluded."""
        flag = Flag(name="almost", variants=[Variant("a", weight=100)], rollout_pct=99)
        excluded = sum(
            1 for i in range(5000)
            if assign_variant(flag, EvalContext(user_id=f"u{i}")) is None
        )
        assert 10 < excluded < 100  # ~50

    def test_fractional_rollout(self):
        """Fractional rollout like 33.33% works."""
        flag = Flag(name="third", variants=[Variant("a", weight=100)], rollout_pct=33.33)
        assigned = sum(
            1 for i in range(3000)
            if assign_variant(flag, EvalContext(user_id=f"u{i}")) is not None
        )
        assert 800 < assigned < 1200  # ~1000

    def test_very_small_rollout(self):
        """0.01% rollout — should still assign some users."""
        flag = Flag(name="micro", variants=[Variant("a", weight=100)], rollout_pct=0.01)
        assigned = sum(
            1 for i in range(100_000)
            if assign_variant(flag, EvalContext(user_id=f"u{i}")) is not None
        )
        # Expected ~10 out of 100k (bucket 0 only)
        assert 0 < assigned < 50


# ── Variant Selection ────────────────────────────────────────────────


class TestVariantSelection:
    def test_deterministic(self, simple_flag: Flag, ctx: EvalContext):
        """Same flag + context always gives the same variant."""
        v1 = assign_variant(simple_flag, ctx)
        v2 = assign_variant(simple_flag, ctx)
        assert v1 is not None and v2 is not None
        assert v1.name == v2.name

    def test_returns_valid_variant(self, simple_flag: Flag):
        """Assigned variant is always from the flag's variant list."""
        names = {v.name for v in simple_flag.variants}
        for i in range(500):
            v = assign_variant(simple_flag, EvalContext(user_id=f"u{i}"))
            assert v is not None
            assert v.name in names

    def test_50_50_weights(self):
        """Equal weights → roughly equal distribution."""
        flag = Flag(
            name="equal",
            variants=[Variant("a", weight=50), Variant("b", weight=50)],
            rollout_pct=100,
        )
        counts = {"a": 0, "b": 0}
        for i in range(2000):
            v = assign_variant(flag, EvalContext(user_id=f"u{i}"))
            assert v is not None
            counts[v.name] += 1
        # Both should be ~1000
        assert 800 < counts["a"] < 1200
        assert 800 < counts["b"] < 1200

    def test_90_10_weights(self):
        """90/10 weights → heavy variant dominates."""
        flag = Flag(
            name="heavy",
            variants=[Variant("heavy", weight=90), Variant("light", weight=10)],
            rollout_pct=100,
        )
        counts = {"heavy": 0, "light": 0}
        for i in range(2000):
            v = assign_variant(flag, EvalContext(user_id=f"u{i}"))
            counts[v.name] += 1
        assert counts["heavy"] > counts["light"] * 5

    def test_single_variant(self):
        """Single variant → always returns that variant."""
        flag = Flag(name="solo", variants=[Variant("only", weight=1)], rollout_pct=100)
        for i in range(100):
            v = assign_variant(flag, EvalContext(user_id=f"u{i}"))
            assert v is not None
            assert v.name == "only"

    def test_three_variants(self):
        """Three variants with different weights all get traffic."""
        flag = Flag(
            name="three",
            variants=[
                Variant("a", weight=60),
                Variant("b", weight=30),
                Variant("c", weight=10),
            ],
            rollout_pct=100,
        )
        counts = {"a": 0, "b": 0, "c": 0}
        for i in range(3000):
            v = assign_variant(flag, EvalContext(user_id=f"u{i}"))
            counts[v.name] += 1
        assert counts["a"] > counts["b"] > counts["c"]
        assert counts["c"] > 0  # Even the smallest variant gets traffic

    def test_five_equal_variants(self):
        """Five equal variants each get ~20%."""
        names = ["v1", "v2", "v3", "v4", "v5"]
        flag = Flag(
            name="five",
            variants=[Variant(n, weight=20) for n in names],
            rollout_pct=100,
        )
        counts = {n: 0 for n in names}
        for i in range(5000):
            v = assign_variant(flag, EvalContext(user_id=f"u{i}"))
            counts[v.name] += 1
        for n in names:
            assert 700 < counts[n] < 1300  # ~1000 ± 300

    def test_very_skewed_weights(self):
        """1 vs 9999 weights → almost all go to heavier."""
        flag = Flag(
            name="skewed",
            variants=[Variant("rare", weight=1), Variant("common", weight=9999)],
            rollout_pct=100,
        )
        counts = {"rare": 0, "common": 0}
        for i in range(5000):
            v = assign_variant(flag, EvalContext(user_id=f"u{i}"))
            counts[v.name] += 1
        assert counts["common"] > counts["rare"] * 100

    def test_weight_of_one(self):
        """Minimum non-zero weight still gets traffic."""
        flag = Flag(
            name="min_weight",
            variants=[Variant("main", weight=99), Variant("tiny", weight=1)],
            rollout_pct=100,
        )
        tiny_count = sum(
            1 for i in range(10000)
            if assign_variant(flag, EvalContext(user_id=f"u{i}")).name == "tiny"
        )
        assert tiny_count > 0

    def test_variant_config_preserved(self):
        """The returned variant's config dict is intact."""
        config = {"model": "gpt-4", "temperature": 0.7, "nested": {"key": [1, 2, 3]}}
        flag = Flag(
            name="cfg",
            variants=[Variant("v", weight=100, config=config)],
            rollout_pct=100,
        )
        v = assign_variant(flag, EvalContext(user_id="u1"))
        assert v is not None
        assert v.config == config


# ── Edge Cases ───────────────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_variants_returns_none(self):
        """Flag with no variants → returns None (fallback)."""
        flag = Flag(name="empty", variants=[], rollout_pct=100)
        assert assign_variant(flag, EvalContext(user_id="u1")) is None

    def test_empty_session_id(self):
        """Empty session_id doesn't affect assignment."""
        flag = Flag(name="f", variants=[Variant("a", weight=100)], rollout_pct=100)
        v1 = assign_variant(flag, EvalContext(user_id="u1", session_id=""))
        v2 = assign_variant(flag, EvalContext(user_id="u1", session_id="anything"))
        # session_id is not used in bucketing, so both should match
        assert v1 is not None and v2 is not None
        assert v1.name == v2.name

    def test_assignment_uses_flag_name_in_hash(self):
        """Changing flag name changes the assignment for the same user."""
        flag_a = Flag(name="flag_a", variants=[Variant("a"), Variant("b")], rollout_pct=100)
        flag_b = Flag(name="flag_b", variants=[Variant("a"), Variant("b")], rollout_pct=100)
        # Not guaranteed to differ per user, but over many users assignments will vary
        different = sum(
            1 for i in range(500)
            if assign_variant(flag_a, EvalContext(user_id=f"u{i}")).name
            != assign_variant(flag_b, EvalContext(user_id=f"u{i}")).name
        )
        assert different > 50  # At least some differ
