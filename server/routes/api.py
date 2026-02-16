"""Dashboard API routes — read-only queries for the frontend."""

from __future__ import annotations

from fastapi import APIRouter

from server.database import get_conn
from server.models import FlagDetail, FlagSummary, TimelinePoint, VariantMetrics

router = APIRouter(prefix="/api/v1/flags", tags=["flags"])


@router.get("", response_model=list[FlagSummary])
def list_flags():
    """List all flags with summary statistics.

    Returns:
        List of FlagSummary objects with variant counts and success rates.
    """
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                a.flag_name,
                array_agg(DISTINCT a.variant_name) AS variants,
                COUNT(*) AS total_assignments,
                COUNT(e.event_id) FILTER (WHERE e.event_type = 'success') AS success_count
            FROM assignments a
            LEFT JOIN events e ON e.assignment_id = a.assignment_id
            GROUP BY a.flag_name
            ORDER BY a.flag_name
            """
        ).fetchall()

    return [
        FlagSummary(
            flag_name=r["flag_name"],
            variants=r["variants"],
            total_assignments=r["total_assignments"],
            success_rate=r["success_count"] / r["total_assignments"]
            if r["total_assignments"] > 0
            else None,
        )
        for r in rows
    ]


@router.get("/{name}", response_model=FlagDetail)
def get_flag(name: str):
    """Get detailed metrics for a specific flag.

    Args:
        name: The flag name to retrieve.

    Returns:
        FlagDetail with per-variant metrics including success rates, latency,
        cost, token usage, and custom events.
    """
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                a.variant_name,
                COUNT(DISTINCT a.assignment_id) AS assignments,
                COUNT(e.event_id) FILTER (WHERE e.event_type = 'success') AS success_count,
                COUNT(e.event_id) FILTER (WHERE e.event_type = 'failure') AS failure_count,
                AVG(ex.latency_ms) AS avg_latency_ms,
                AVG(ex.cost) AS avg_cost,
                AVG(ex.input_tokens) AS avg_input_tokens,
                AVG(ex.output_tokens) AS avg_output_tokens
            FROM assignments a
            LEFT JOIN executions ex ON ex.assignment_id = a.assignment_id
            LEFT JOIN events e ON e.assignment_id = a.assignment_id
            WHERE a.flag_name = %s
            GROUP BY a.variant_name
            ORDER BY a.variant_name
            """,
            (name,),
        ).fetchall()

        # Custom events
        custom_rows = conn.execute(
            """
            SELECT a.variant_name, e.event_name, COUNT(*) AS cnt
            FROM events e
            JOIN assignments a ON a.assignment_id = e.assignment_id
            WHERE a.flag_name = %s AND e.event_type = 'custom'
            GROUP BY a.variant_name, e.event_name
            """,
            (name,),
        ).fetchall()

    custom_map: dict[str, dict[str, int]] = {}
    for cr in custom_rows:
        custom_map.setdefault(cr["variant_name"], {})[cr["event_name"]] = cr["cnt"]

    total = sum(r["assignments"] for r in rows)
    variants = [
        VariantMetrics(
            variant_name=r["variant_name"],
            assignments=r["assignments"],
            success_count=r["success_count"],
            failure_count=r["failure_count"],
            success_rate=r["success_count"] / r["assignments"]
            if r["assignments"] > 0
            else None,
            avg_latency_ms=float(r["avg_latency_ms"]) if r["avg_latency_ms"] else None,
            avg_cost=float(r["avg_cost"]) if r["avg_cost"] else None,
            avg_input_tokens=float(r["avg_input_tokens"]) if r["avg_input_tokens"] else None,
            avg_output_tokens=float(r["avg_output_tokens"]) if r["avg_output_tokens"] else None,
            custom_events=custom_map.get(r["variant_name"], {}),
        )
        for r in rows
    ]

    return FlagDetail(flag_name=name, total_assignments=total, variants=variants)


@router.get("/{name}/timeline", response_model=list[TimelinePoint])
def get_timeline(name: str):
    """Get daily timeline data for a flag.

    Args:
        name: The flag name to retrieve timeline for.

    Returns:
        List of TimelinePoint objects with daily aggregates by variant.
    """
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                DATE(a.assigned_at) AS date,
                a.variant_name,
                COUNT(*) AS assignments,
                COUNT(e.event_id) FILTER (WHERE e.event_type = 'success') AS success_count,
                AVG(ex.latency_ms) AS avg_latency_ms,
                AVG(ex.cost) AS avg_cost
            FROM assignments a
            LEFT JOIN executions ex ON ex.assignment_id = a.assignment_id
            LEFT JOIN events e ON e.assignment_id = a.assignment_id
            WHERE a.flag_name = %s
            GROUP BY DATE(a.assigned_at), a.variant_name
            ORDER BY date, a.variant_name
            """,
            (name,),
        ).fetchall()

    return [
        TimelinePoint(
            date=str(r["date"]),
            variant_name=r["variant_name"],
            assignments=r["assignments"],
            success_rate=r["success_count"] / r["assignments"]
            if r["assignments"] > 0
            else None,
            avg_latency_ms=float(r["avg_latency_ms"]) if r["avg_latency_ms"] else None,
            avg_cost=float(r["avg_cost"]) if r["avg_cost"] else None,
        )
        for r in rows
    ]
