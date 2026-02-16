"""ServerStorage — HTTP storage backend that buffers and flushes to modelab-server."""

from __future__ import annotations

import atexit
import json
import logging
import threading
import urllib.request
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from modelab._types import AssignmentRecord, EventRecord, ExecutionRecord

logger = logging.getLogger("modelab")

_FLUSH_SIZE = 50
_FLUSH_INTERVAL = 5.0  # seconds


def _default_serializer(obj: Any) -> str:
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Not serializable: {type(obj)}")


class ServerStorage:
    """HTTP storage that buffers records and flushes to the modelab server."""

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._lock = threading.Lock()
        self._assignments: list[dict[str, Any]] = []
        self._executions: list[dict[str, Any]] = []
        self._events: list[dict[str, Any]] = []

        # Background flush timer
        self._timer: threading.Timer | None = None
        self._start_timer()
        atexit.register(self.flush)

    def _start_timer(self) -> None:
        self._timer = threading.Timer(_FLUSH_INTERVAL, self._timer_flush)
        self._timer.daemon = True
        self._timer.start()

    def _timer_flush(self) -> None:
        self.flush()
        self._start_timer()

    def save_assignment(self, record: AssignmentRecord) -> None:
        with self._lock:
            self._assignments.append(asdict(record))
            if len(self._assignments) >= _FLUSH_SIZE:
                self._flush_locked("assignments", self._assignments)
                self._assignments = []

    def save_execution(self, record: ExecutionRecord) -> None:
        with self._lock:
            self._executions.append(asdict(record))
            if len(self._executions) >= _FLUSH_SIZE:
                self._flush_locked("executions", self._executions)
                self._executions = []

    def save_event(self, record: EventRecord) -> None:
        with self._lock:
            self._events.append(asdict(record))
            if len(self._events) >= _FLUSH_SIZE:
                self._flush_locked("events", self._events)
                self._events = []

    def flush(self) -> None:
        with self._lock:
            if self._assignments:
                self._flush_locked("assignments", self._assignments)
                self._assignments = []
            if self._executions:
                self._flush_locked("executions", self._executions)
                self._executions = []
            if self._events:
                self._flush_locked("events", self._events)
                self._events = []

    def _flush_locked(self, endpoint: str, records: list[dict[str, Any]]) -> None:
        url = f"{self._base_url}/api/v1/ingest/{endpoint}"
        data = json.dumps(records, default=_default_serializer).encode()
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                **({"X-API-Key": self._api_key} if self._api_key else {}),
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp.read()
        except Exception:
            logger.warning("Failed to flush %d %s to %s", len(records), endpoint, url, exc_info=True)
