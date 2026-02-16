"""Exception hierarchy for modelab."""

from __future__ import annotations


class ModelabError(Exception):
    """Base exception for all modelab errors."""


class NotInitializedError(ModelabError):
    """Raised when modelab.assign() is called before modelab.init()."""

    def __init__(self) -> None:
        super().__init__("modelab.init() must be called before assign()")


class FlagNotFoundError(ModelabError):
    """Raised when a flag name is not in the registry."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Flag not found: {name!r}")
        self.name = name


class InvalidFlagError(ModelabError):
    """Raised when a Flag definition is invalid."""
