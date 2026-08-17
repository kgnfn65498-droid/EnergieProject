from __future__ import annotations

import copy
import threading
from typing import Any, Callable


class AssistantAnalysisCache:
    """Small read-only in-memory cache for already validated assistant context."""

    def __init__(self, builder: Callable[..., dict[str, Any]]) -> None:
        self._builder = builder
        self._lock = threading.RLock()
        self._contexts: dict[int | None, dict[str, Any]] = {}

    @staticmethod
    def _key(year: int | None) -> int | None:
        return int(year) if year is not None else None

    def refresh(self, *, year: int | None = None) -> dict[str, Any]:
        key = self._key(year)
        context = self._builder(year=year)
        if not isinstance(context, dict):
            raise TypeError("assistant analysis builder must return a dict")
        stored = copy.deepcopy(context)
        with self._lock:
            self._contexts[key] = stored
        return copy.deepcopy(stored)

    def get(self, *, year: int | None = None) -> dict[str, Any]:
        key = self._key(year)
        with self._lock:
            context = self._contexts.get(key)
            if context is not None:
                return copy.deepcopy(context)
        return self.refresh(year=year)
