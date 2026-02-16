"""modelab — provider-agnostic A/B testing for LLM systems."""

from __future__ import annotations

import json
import logging
import urllib.request
from typing import Any, Sequence

from modelab._assignment import Assignment
from modelab._engine import assign_variant
from modelab._errors import FlagNotFoundError, NotInitializedError
from modelab._server_storage import ServerStorage
from modelab._state import _global_state
from modelab._types import (
    AssignmentRecord,
    EvalContext,
    Flag,
    Variant,
)

__all__ = [
    "init",
    "assign",
    "evaluate",
    "Flag",
    "Variant",
    "EvalContext",
    "Assignment",
]


def init(
    server: str,
    flags: Sequence[Flag] = (),
    api_key: str = "",
) -> None:
    """Initialize modelab with a server URL and flag definitions.

    Args:
        server: The modelab server URL (e.g. "http://localhost:8100").
        flags: The experiment flags to register.
        api_key: Optional API key for server authentication.
    """
    storage = ServerStorage(server, api_key=api_key)
    _global_state.configure(storage, list(flags), server_url=server)


def assign(flag_name: str, ctx: EvalContext) -> Assignment | None:
    """Assign a variant for the given flag and context.

    Returns None if the user is outside the rollout percentage.
    Raises NotInitializedError if init() hasn't been called.
    Raises FlagNotFoundError if the flag name isn't registered.
    """
    if not _global_state.initialized:
        raise NotInitializedError()

    flag = _global_state.flags.get(flag_name)
    if flag is None:
        raise FlagNotFoundError(flag_name)

    variant = assign_variant(flag, ctx)
    if variant is None:
        return None

    storage = _global_state.storage
    assert storage is not None

    record = AssignmentRecord(
        flag_name=flag_name,
        variant_name=variant.name,
        user_id=ctx.user_id,
        session_id=ctx.session_id,
        config_json=dict(variant.config),
    )

    try:
        storage.save_assignment(record)
    except Exception:
        logging.getLogger("modelab").warning(
            "Failed to save assignment for %s", flag_name, exc_info=True
        )

    return Assignment(
        flag_name=flag_name,
        variant_name=variant.name,
        config=dict(variant.config),
        context=ctx,
        storage=storage,
        assignment_id=record.assignment_id,
    )


def evaluate(flag_name: str) -> dict[str, Any]:
    """Fetch per-variant metrics for a flag from the server.

    Flushes any buffered data, then queries the server's
    GET /api/v1/flags/{flag_name} endpoint.

    Raises NotInitializedError if init() hasn't been called.
    Raises FlagNotFoundError if the flag name isn't registered.
    """
    if not _global_state.initialized:
        raise NotInitializedError()

    if flag_name not in _global_state.flags:
        raise FlagNotFoundError(flag_name)

    storage = _global_state.storage
    assert storage is not None
    storage.flush()

    url = f"{_global_state.server_url.rstrip('/')}/api/v1/flags/{flag_name}"
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def reset() -> None:
    """Reset global state to uninitialized.

    Clears all flags, storage, and server URL. Primarily used for testing
    to ensure clean state between test runs.
    """
    _global_state.reset()
