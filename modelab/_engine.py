"""Deterministic assignment engine: hash → bucket → rollout gate → variant."""

from __future__ import annotations

import hashlib

from modelab._types import EvalContext, Flag, Variant

BUCKET_COUNT = 10_000


def _bucket(flag_name: str, user_id: str) -> int:
    """Deterministic bucket in [0, BUCKET_COUNT) from flag + user."""
    key = f"{flag_name}:{user_id}"
    digest = hashlib.md5(key.encode()).hexdigest()
    return int(digest, 16) % BUCKET_COUNT


def assign_variant(flag: Flag, ctx: EvalContext) -> Variant | None:
    """Return the assigned Variant, or None if outside rollout."""
    bucket = _bucket(flag.name, ctx.user_id)

    # Rollout gate: rollout_pct of 100 means buckets 0–9999 pass
    rollout_threshold = int(flag.rollout_pct / 100.0 * BUCKET_COUNT)
    if bucket >= rollout_threshold:
        return None

    # Weighted variant selection within the rollout population
    total_weight = sum(v.weight for v in flag.variants)
    if total_weight == 0:
        return flag.variants[0] if flag.variants else None
    point = bucket % total_weight
    cumulative = 0
    for variant in flag.variants:
        cumulative += variant.weight
        if point < cumulative:
            return variant

    # Fallback (shouldn't happen if weights > 0)
    return flag.variants[-1] if flag.variants else None
