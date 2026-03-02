"""Qdrant vector DB connector.

Required SDK: qdrant-client  (pip install qdrant-client)
Falls back gracefully if the package is not installed.

Expected properties:
  url          (required) – e.g. http://localhost:6333
  api_key      (optional, secret)
  grpc_port    (optional, integer)
  prefer_grpc  (optional, boolean)
"""

from __future__ import annotations

from typing import Any

from app.connectors import BaseVectorConnector
from app.schemas.vectordb import ConnectionTestResult


class QdrantConnector(BaseVectorConnector):

    def test_connection(self) -> ConnectionTestResult:
        url: str = self.properties.get("url", "")
        api_key: str | None = self.properties.get("api_key") or None
        prefer_grpc: bool = bool(self.properties.get("prefer_grpc", False))
        grpc_port: int | None = self.properties.get("grpc_port") or None

        if not url:
            return ConnectionTestResult(
                success=False,
                message="Connection failed",
                detail="'url' property is required for Qdrant",
            )

        try:
            from qdrant_client import QdrantClient  # type: ignore[import]
        except ImportError:
            # SDK not installed – fall back to a plain HTTP health-check
            return self._http_health_check(url)

        def _connect() -> None:
            kwargs: dict[str, Any] = dict(url=url, prefer_grpc=prefer_grpc)
            if api_key:
                kwargs["api_key"] = api_key
            if grpc_port:
                kwargs["grpc_port"] = grpc_port
            client = QdrantClient(**kwargs)
            client.get_collections()

        try:
            _, elapsed = self._timed(_connect)
            return ConnectionTestResult(
                success=True,
                message="Successfully connected to Qdrant",
                latency_ms=elapsed,
            )
        except Exception as exc:
            return ConnectionTestResult(
                success=False,
                message="Connection failed",
                detail=str(exc),
            )

    # ── Fallback ──────────────────────────────────────────────────────────────

    @staticmethod
    def _http_health_check(url: str) -> ConnectionTestResult:
        """Simple HTTP GET to /healthz when the SDK is not available."""
        import urllib.request
        import urllib.error

        health_url = url.rstrip("/") + "/healthz"
        try:
            with urllib.request.urlopen(health_url, timeout=5) as resp:
                if resp.status == 200:
                    return ConnectionTestResult(
                        success=True,
                        message="Qdrant health-check OK (SDK not installed, HTTP fallback)",
                    )
                return ConnectionTestResult(
                    success=False,
                    message="Qdrant health-check returned unexpected status",
                    detail=f"HTTP {resp.status}",
                )
        except Exception as exc:
            return ConnectionTestResult(
                success=False,
                message="Connection failed (HTTP fallback, SDK not installed)",
                detail=str(exc),
            )
