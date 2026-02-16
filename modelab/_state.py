"""Module-level singleton state for modelab."""

from __future__ import annotations

from typing import TYPE_CHECKING

from modelab._errors import InvalidFlagError
from modelab._types import Flag

if TYPE_CHECKING:
    from modelab._server_storage import ServerStorage


class _State:
    def __init__(self) -> None:
        self.storage: ServerStorage | None = None
        self.flags: dict[str, Flag] = {}
        self.server_url: str = ""

    def configure(self, storage: ServerStorage, flags: list[Flag], server_url: str = "") -> None:
        for flag in flags:
            if not flag.variants:
                raise InvalidFlagError(f"Flag {flag.name!r} has no variants")
            if not (0 <= flag.rollout_pct <= 100):
                raise InvalidFlagError(f"Flag {flag.name!r} rollout_pct must be 0-100, got {flag.rollout_pct}")
        self.storage = storage
        self.flags = {f.name: f for f in flags}
        self.server_url = server_url

    def reset(self) -> None:
        self.storage = None
        self.flags = {}
        self.server_url = ""

    @property
    def initialized(self) -> bool:
        return self.storage is not None


_global_state = _State()
