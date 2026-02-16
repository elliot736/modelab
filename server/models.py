"""Pydantic request/response schemas for the server API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


# ── Ingest request models ───────────────────────────────────────────


class AssignmentIn(BaseModel):
    assignment_id: str
    flag_name: str
    variant_name: str
    user_id: str
    session_id: str = ""
    config_json: dict[str, Any] = {}
    assigned_at: datetime


class ExecutionIn(BaseModel):
    assignment_id: str
    latency_ms: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost: float | None = None
    error: str | None = None
    metadata_json: dict[str, Any] = {}
    recorded_at: datetime


class EventIn(BaseModel):
    event_id: str
    assignment_id: str
    event_type: str
    event_name: str = ""
    payload_json: dict[str, Any] = {}
    created_at: datetime


# ── Response models ─────────────────────────────────────────────────


class FlagSummary(BaseModel):
    flag_name: str
    variants: list[str]
    total_assignments: int
    success_rate: float | None


class VariantMetrics(BaseModel):
    variant_name: str
    assignments: int
    success_count: int
    failure_count: int
    success_rate: float | None
    avg_latency_ms: float | None
    avg_cost: float | None
    avg_input_tokens: float | None
    avg_output_tokens: float | None
    custom_events: dict[str, int]


class FlagDetail(BaseModel):
    flag_name: str
    total_assignments: int
    variants: list[VariantMetrics]


class TimelinePoint(BaseModel):
    date: str
    variant_name: str
    assignments: int
    success_rate: float | None
    avg_latency_ms: float | None
    avg_cost: float | None


class IngestResponse(BaseModel):
    inserted: int
