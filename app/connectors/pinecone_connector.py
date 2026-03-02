"""Pinecone vector DB connector.

Required SDK: pinecone-client  (pip install pinecone-client)
Falls back gracefully if the package is not installed.

Expected properties:
  api_key        (required, secret)
  environment    (required) – e.g. us-east-1-aws  (only for legacy API)
  index_name     (optional)
  namespace      (optional)
  host           (optional) – for serverless / newer SDK versions pass 'host' directly
"""

from __future__ import annotations

from app.connectors import BaseVectorConnector
from app.schemas.vectordb import ConnectionTestResult


class PineconeConnector(BaseVectorConnector):

    def test_connection(self) -> ConnectionTestResult:
        api_key: str = self.properties.get("api_key", "")
        environment: str = self.properties.get("environment", "")
        host: str = self.properties.get("host", "")

        if not api_key:
            return ConnectionTestResult(
                success=False,
                message="Connection failed",
                detail="'api_key' property is required for Pinecone",
            )

        try:
            from pinecone import Pinecone  # type: ignore[import]  # SDK v3+
        except ImportError:
            return self._api_health_check(api_key)

        def _connect() -> None:
            pc = Pinecone(api_key=api_key)
            # List indexes to verify credentials & connectivity
            pc.list_indexes()

        try:
            _, elapsed = self._timed(_connect)
            return ConnectionTestResult(
                success=True,
                message="Successfully connected to Pinecone",
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
    def _api_health_check(api_key: str) -> ConnectionTestResult:
        """Minimal REST call to Pinecone API when SDK is absent."""
        import urllib.request
        import urllib.error

        req = urllib.request.Request(
            "https://api.pinecone.io/indexes",
            headers={"Api-Key": api_key, "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                if resp.status == 200:
                    return ConnectionTestResult(
                        success=True,
                        message="Pinecone API reachable (SDK not installed, HTTP fallback)",
                    )
                return ConnectionTestResult(
                    success=False,
                    message="Pinecone API returned unexpected status",
                    detail=f"HTTP {resp.status}",
                )
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                return ConnectionTestResult(
                    success=False,
                    message="Connection failed – invalid API key",
                    detail=str(exc),
                )
            return ConnectionTestResult(
                success=False,
                message="Connection failed",
                detail=str(exc),
            )
        except Exception as exc:
            return ConnectionTestResult(
                success=False,
                message="Connection failed (HTTP fallback, SDK not installed)",
                detail=str(exc),
            )
