"""
Abstract base class for vector DB connectors.

Every concrete connector must implement `test_connection()`.
The connectors intentionally do NOT require the vendor SDK at import time —
each one catches `ImportError` and returns a clear failure result so the
application starts cleanly even without optional dependencies installed.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

from app.schemas.vectordb import ConnectionTestResult


class BaseVectorConnector(ABC):
    """Abstract connector.  Subclasses receive the raw properties dict."""

    def __init__(self, properties: dict[str, Any]) -> None:
        self.properties = properties

    @abstractmethod
    def test_connection(self) -> ConnectionTestResult:
        """
        Attempt to connect to the vector DB and return a result.

        Must never raise — all exceptions should be caught and returned
        as a failed ConnectionTestResult.
        """

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _timed(fn):  # type: ignore[override]
        """Run fn(), return (result, elapsed_ms)."""
        start = time.perf_counter()
        result = fn()
        elapsed = (time.perf_counter() - start) * 1000
        return result, round(elapsed, 2)
