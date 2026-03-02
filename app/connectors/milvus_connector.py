"""Milvus vector DB connector.

Required SDK: pymilvus  (pip install pymilvus)
Falls back gracefully if the package is not installed.

Expected properties:
  host             (required) – e.g. localhost
  port             (optional, integer, default 19530)
  user             (optional)
  password         (optional, secret)
  secure           (optional, boolean, default false)
  db_name          (optional)
"""

from __future__ import annotations

from app.connectors import BaseVectorConnector
from app.schemas.vectordb import ConnectionTestResult


class MilvusConnector(BaseVectorConnector):

    def test_connection(self) -> ConnectionTestResult:
        host: str = self.properties.get("host", "")
        port: int = int(self.properties.get("port", 19530))
        user: str = self.properties.get("user", "")
        password: str = self.properties.get("password", "")
        secure: bool = bool(self.properties.get("secure", False))
        db_name: str = self.properties.get("db_name", "default")

        if not host:
            return ConnectionTestResult(
                success=False,
                message="Connection failed",
                detail="'host' property is required for Milvus",
            )

        try:
            from pymilvus import connections, utility  # type: ignore[import]
        except ImportError:
            return self._tcp_check(host, port)

        alias = f"test_{host}_{port}"

        def _connect() -> None:
            connections.connect(
                alias=alias,
                host=host,
                port=str(port),
                user=user or None,
                password=password or None,
                secure=secure,
                db_name=db_name,
            )
            utility.get_server_version(using=alias)

        try:
            _, elapsed = self._timed(_connect)
            return ConnectionTestResult(
                success=True,
                message="Successfully connected to Milvus",
                latency_ms=elapsed,
            )
        except Exception as exc:
            return ConnectionTestResult(
                success=False,
                message="Connection failed",
                detail=str(exc),
            )
        finally:
            # Always disconnect test alias
            try:
                from pymilvus import connections  # type: ignore[import]
                connections.disconnect(alias)
            except Exception:
                pass

    # ── Fallback ──────────────────────────────────────────────────────────────

    @staticmethod
    def _tcp_check(host: str, port: int) -> ConnectionTestResult:
        """Raw TCP connect when pymilvus is not installed."""
        import socket

        try:
            with socket.create_connection((host, port), timeout=5):
                return ConnectionTestResult(
                    success=True,
                    message=f"TCP connection to {host}:{port} succeeded (SDK not installed, TCP fallback)",
                )
        except Exception as exc:
            return ConnectionTestResult(
                success=False,
                message="Connection failed (TCP fallback, SDK not installed)",
                detail=str(exc),
            )
