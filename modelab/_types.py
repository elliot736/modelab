"""Core types for modelab: Flag, Variant, EvalContext, records, Storage protocol."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class Variant:
    """A single variant within a flag."""

    name: str
    weight: int = 50
    config: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Flag:
    """An experiment flag with one or more variants."""

    name: str
    variants: list[Variant] = field(default_factory=list)
    rollout_pct: float = 100.0


@dataclass(frozen=True)
class EvalContext:
    """Context for assignment — identifies who is being assigned."""

    user_id: str
    session_id: str = ""


# ── Records (persisted to storage) ──────────────────────────────────


@dataclass
class AssignmentRecord:
    assignment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    flag_name: str = ""
    variant_name: str = ""
    user_id: str = ""
    session_id: str = ""
    config_json: dict[str, Any] = field(default_factory=dict)
    assigned_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ExecutionRecord:
    assignment_id: str = ""
    latency_ms: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost: float | None = None
    error: str | None = None
    metadata_json: dict[str, Any] = field(default_factory=dict)
    recorded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class EventRecord:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    assignment_id: str = ""
    event_type: str = ""  # success / failure / custom
    event_name: str = ""  # for custom events
    payload_json: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
