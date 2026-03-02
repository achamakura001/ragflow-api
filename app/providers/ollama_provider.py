"""
Ollama embedding provider.

Required property : ``base_url`` (e.g. http://localhost:11434)
Optional property : ``filter_embedding`` (boolean, default true – when true only
                    returns models that have an embedding-relevant name)

Uses raw HTTP; no SDK dependency.
Calls GET {base_url}/api/tags to list local models.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from app.providers import BaseEmbeddingProvider
from app.schemas.embedding import ConfigTestResult, EmbeddingModel, FetchModelsResult

logger = logging.getLogger(__name__)

_EMBED_KEYWORDS = ("embed", "nomic", "minilm", "bge", "e5", "gte", "all-minilm")


def _looks_like_embedding(name: str) -> bool:
    lower = name.lower()
    return any(kw in lower for kw in _EMBED_KEYWORDS)


class OllamaProvider(BaseEmbeddingProvider):
    """Ollama local model server provider."""

    def _base_url(self) -> str | None:
        v = str(self._props.get("base_url", "")).strip()
        return v.rstrip("/") if v else None

    def _filter(self) -> bool:
        v = self._props.get("filter_embedding", True)
        if isinstance(v, bool):
            return v
        return str(v).lower() not in ("false", "0", "no")

    # ── test_connection ───────────────────────────────────────────────────────

    def test_connection(self) -> ConfigTestResult:
        base_url = self._base_url()
        if not base_url:
            logger.warning("Ollama test_connection: 'base_url' property is missing")
            return ConfigTestResult(
                success=False,
                message="Connection failed",
                detail="'base_url' property is required for Ollama",
            )

        url = f"{base_url}/api/tags"
        logger.info("Ollama test_connection: GET %s", url)
        try:
            def _do():
                with urllib.request.urlopen(url, timeout=10) as r:
                    return r.status
            status, ms = self._timed(_do)
            if status == 200:
                logger.info("Ollama test_connection: success (HTTP 200) in %.1f ms", ms)
                return ConfigTestResult(success=True, message="Connected successfully", latency_ms=ms)
            logger.warning("Ollama test_connection: unexpected HTTP %s from %s", status, url)
            return ConfigTestResult(
                success=False, message=f"Unexpected HTTP {status}", latency_ms=ms
            )
        except urllib.error.HTTPError as exc:
            logger.warning("Ollama test_connection: HTTP error %s %s from %s", exc.code, exc.reason, url)
            return ConfigTestResult(success=False, message="Connection failed", detail=f"HTTP {exc.code}: {exc.reason}")
        except Exception as exc:
            logger.exception("Ollama test_connection: unexpected error connecting to %s", url)
            return ConfigTestResult(success=False, message="Connection failed", detail=str(exc))

    # ── fetch_models ──────────────────────────────────────────────────────────

    def fetch_models(self) -> FetchModelsResult:
        base_url = self._base_url()
        if not base_url:
            logger.warning("Ollama fetch_models: 'base_url' property is missing")
            return FetchModelsResult(
                success=False, provider_slug="ollama",
                message="'base_url' property is required for Ollama",
            )

        url = f"{base_url}/api/tags"
        logger.info("Ollama fetch_models: GET %s (filter_embedding=%s)", url, self._filter())
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            logger.warning("Ollama fetch_models: HTTP error %s %s from %s", exc.code, exc.reason, url)
            return FetchModelsResult(
                success=False, provider_slug="ollama",
                message="Failed to fetch models", detail=f"HTTP {exc.code}: {exc.reason}",
            )
        except Exception as exc:
            logger.exception("Ollama fetch_models: unexpected error fetching from %s", url)
            return FetchModelsResult(
                success=False, provider_slug="ollama",
                message="Failed to fetch models", detail=str(exc),
            )

        all_models = data.get("models", [])
        if self._filter():
            models = [
                EmbeddingModel(
                    id=m.get("name", ""),
                    display_name=m.get("name", ""),
                    description=m.get("details", {}).get("family"),
                )
                for m in all_models
                if _looks_like_embedding(m.get("name", ""))
            ]
        else:
            models = [
                EmbeddingModel(
                    id=m.get("name", ""),
                    display_name=m.get("name", ""),
                    description=m.get("details", {}).get("family"),
                )
                for m in all_models
            ]

        logger.info("Ollama fetch_models: returned %d model(s) (from %d total)", len(models), len(all_models))
        return FetchModelsResult(
            success=True, provider_slug="ollama",
            models=models, message=f"Fetched {len(models)} model(s)",
        )
