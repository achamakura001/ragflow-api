"""
Abstract base class for embedding provider implementations.

Each concrete provider must implement:
  - ``test_connection()``  → ConfigTestResult
  - ``fetch_models()``     → FetchModelsResult

Both methods are synchronous so they can be safely offloaded to a thread pool
via ``asyncio.get_event_loop().run_in_executor(None, …)`` in the service layer.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any

from app.schemas.embedding import ConfigTestResult, FetchModelsResult

logger = logging.getLogger(__name__)


class BaseEmbeddingProvider(ABC):
    """Base class for all embedding provider implementations."""

    def __init__(self, properties: dict[str, Any]) -> None:
        self._props = properties

    # ── Abstract interface ────────────────────────────────────────────────────

    @abstractmethod
    def test_connection(self) -> ConfigTestResult:
        """Verify credentials are valid and the provider endpoint is reachable."""

    @abstractmethod
    def fetch_models(self) -> FetchModelsResult:
        """Call the provider API and return all available embedding models."""

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get(self, key: str, default: Any = None) -> Any:
        return self._props.get(key, default)

    def _timed(self, fn) -> tuple[Any, float]:
        """Run fn() and return (result, elapsed_ms)."""
        start = time.monotonic()
        result = fn()
        elapsed = (time.monotonic() - start) * 1000
        logger.debug("%s._timed completed in %.1f ms", self.__class__.__name__, elapsed)
        return result, elapsed
