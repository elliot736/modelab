"""Assignment class — the main object returned by modelab.assign()."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from modelab._types import (
    EvalContext,
    EventRecord,
    ExecutionRecord,
)

if TYPE_CHECKING:
    from modelab._server_storage import ServerStorage

logger = logging.getLogger("modelab")


def _extract_usage_from_response(response: Any) -> tuple[int | None, int | None]:
    """Duck-type token usage from a provider response object.

    Tries OpenAI-style attrs first (usage.prompt_tokens / completion_tokens),
    then Anthropic-style (usage.input_tokens / output_tokens).
    Returns (input_tokens, output_tokens) or (None, None) if not found.
    """
    usage = getattr(response, "usage", None)
    if usage is None:
        return None, None

    # OpenAI: usage.prompt_tokens / usage.completion_tokens
    prompt = getattr(usage, "prompt_tokens", None)
    completion = getattr(usage, "completion_tokens", None)
    if prompt is not None or completion is not None:
        return prompt, completion

    # Anthropic: usage.input_tokens / usage.output_tokens
    inp = getattr(usage, "input_tokens", None)
    out = getattr(usage, "output_tokens", None)
    if inp is not None or out is not None:
        return inp, out

    return None, None


class Assignment:
    """Represents a variant assignment for a specific evaluation context."""

    def __init__(
        self,
        flag_name: str,
        variant_name: str,
        config: dict[str, Any],
        context: EvalContext,
        storage: ServerStorage,
        assignment_id: str,
    ) -> None:
        self._flag_name = flag_name
        self._variant_name = variant_name
        self._config = config
        self._context = context
        self._storage = storage
        self._assignment_id = assignment_id

    @property
    def flag_name(self) -> str:
        return self._flag_name

    @property
    def variant_name(self) -> str:
        return self._variant_name

    @property
    def config(self) -> dict[str, Any]:
        return self._config

    @property
    def context(self) -> EvalContext:
        return self._context

    @property
    def assignment_id(self) -> str:
        return self._assignment_id

    def record(
        self,
        response: Any = None,
        *,
        latency_ms: float | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        cost: float | None = None,
        error: str | None = None,
        **metadata: Any,
    ) -> None:
        """Record execution metrics, optionally extracting tokens from a provider response.

        If ``response`` is passed, token counts are duck-typed from
        ``response.usage`` (OpenAI and Anthropic formats).
        Explicit keyword arguments always override extracted values.
        """
        if response is not None:
            extracted_in, extracted_out = _extract_usage_from_response(response)
            if input_tokens is None:
                input_tokens = extracted_in
            if output_tokens is None:
                output_tokens = extracted_out

        self._save_execution(
            ExecutionRecord(
                assignment_id=self._assignment_id,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=cost,
                error=error,
                metadata_json=metadata,
            )
        )

    def mark_success(self, payload: dict[str, Any] | None = None) -> None:
        """Mark this assignment as a success event.

        Args:
            payload: Optional additional data to attach to the event.
        """
        self._save_event("success", "", payload or {})

    def mark_failure(self, payload: dict[str, Any] | None = None) -> None:
        """Mark this assignment as a failure event.

        Args:
            payload: Optional additional data to attach to the event.
        """
        self._save_event("failure", "", payload or {})

    def mark_custom_event(self, name: str, payload: dict[str, Any] | None = None) -> None:
        """Mark a custom event for this assignment.

        Args:
            name: The name of the custom event (e.g., "copied", "dismissed").
            payload: Optional additional data to attach to the event.
        """
        self._save_event("custom", name, payload or {})

    def _save_execution(self, record: ExecutionRecord) -> None:
        try:
            self._storage.save_execution(record)
        except Exception:
            logger.warning("Failed to save execution for %s", self._assignment_id, exc_info=True)

    def _save_event(self, event_type: str, event_name: str, payload: dict[str, Any]) -> None:
        try:
            self._storage.save_event(
                EventRecord(
                    assignment_id=self._assignment_id,
                    event_type=event_type,
                    event_name=event_name,
                    payload_json=payload,
                )
            )
        except Exception:
            logger.warning("Failed to save event for %s", self._assignment_id, exc_info=True)
