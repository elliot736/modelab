"""Ingest routes — receive data from the SDK."""

from __future__ import annotations

import json

from fastapi import APIRouter, Body

from server.database import get_conn
from server.models import AssignmentIn, EventIn, ExecutionIn, IngestResponse

router = APIRouter(prefix="/api/v1/ingest", tags=["ingest"])


@router.post("/assignments", response_model=IngestResponse)
def ingest_assignments(records: list[AssignmentIn] = Body(default=[])):
    """Ingest assignment records from the SDK.

    Args:
        records: List of assignment records to insert into the database.

    Returns:
        IngestResponse with the count of inserted records.
    """
    with get_conn() as conn:
        for r in records:
            conn.execute(
                """INSERT INTO assignments
                   (assignment_id, flag_name, variant_name, user_id, session_id, config_json, assigned_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (assignment_id) DO NOTHING""",
                (
                    r.assignment_id,
                    r.flag_name,
                    r.variant_name,
                    r.user_id,
                    r.session_id,
                    json.dumps(r.config_json),
                    r.assigned_at,
                ),
            )
        conn.commit()
    return IngestResponse(inserted=len(records))


@router.post("/executions", response_model=IngestResponse)
def ingest_executions(records: list[ExecutionIn] = Body(default=[])):
    """Ingest execution records from the SDK.

    Args:
        records: List of execution records (latency, tokens, cost) to insert.

    Returns:
        IngestResponse with the count of inserted records.
    """
    with get_conn() as conn:
        for r in records:
            conn.execute(
                """INSERT INTO executions
                   (assignment_id, latency_ms, input_tokens, output_tokens, cost, error, metadata_json, recorded_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (assignment_id) DO NOTHING""",
                (
                    r.assignment_id,
                    r.latency_ms,
                    r.input_tokens,
                    r.output_tokens,
                    r.cost,
                    r.error,
                    json.dumps(r.metadata_json),
                    r.recorded_at,
                ),
            )
        conn.commit()
    return IngestResponse(inserted=len(records))


@router.post("/events", response_model=IngestResponse)
def ingest_events(records: list[EventIn] = Body(default=[])):
    """Ingest event records from the SDK.

    Args:
        records: List of event records (success, failure, custom) to insert.

    Returns:
        IngestResponse with the count of inserted records.
    """
    with get_conn() as conn:
        for r in records:
            conn.execute(
                """INSERT INTO events
                   (event_id, assignment_id, event_type, event_name, payload_json, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (event_id) DO NOTHING""",
                (
                    r.event_id,
                    r.assignment_id,
                    r.event_type,
                    r.event_name,
                    json.dumps(r.payload_json),
                    r.created_at,
                ),
            )
        conn.commit()
    return IngestResponse(inserted=len(records))
