"""
OpenAI embedding provider.

Required property : ``api_key``  (secret)
Optional property : ``base_url`` (default: https://api.openai.com/v1)

Uses the openai SDK when installed; falls back to raw urllib HTTP otherwise.
Filters the /v1/models response to return only embedding-capable models
(those whose id contains "embedding" or starts with "text-embedding").
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

from app.providers import BaseEmbeddingProvider
from app.schemas.embedding import ConfigTestResult, EmbeddingModel, FetchModelsResult

logger = logging.getLogger(__name__)

_DEFAULT_BASE = "https://api.openai.com/v1"
_EMBED_KEYWORDS = ("embedding", "text-embedding")


def _is_embedding_model(model_id: str) -> bool:
    lid = model_id.lower()
    return any(kw in lid for kw in _EMBED_KEYWORDS)


class OpenAIProvider(BaseEmbeddingProvider):
    """OpenAI embedding provider."""

    def _api_key(self) -> str | None:
        return str(self._props.get("api_key", "")).strip() or None

    def _base_url(self) -> str:
        return str(self._props.get("base_url", _DEFAULT_BASE)).rstrip("/")

    # ── test_connection ───────────────────────────────────────────────────────

    def test_connection(self) -> ConfigTestResult:
        api_key = self._api_key()
        if not api_key:
            logger.warning("OpenAI test_connection: 'api_key' property is missing")
            return ConfigTestResult(
                success=False,
                message="Connection failed",
                detail="'api_key' property is required for OpenAI",
            )

        logger.info("OpenAI test_connection: attempting via SDK (base_url=%s)", self._base_url())
        try:
            sdk_result, ms = self._timed(lambda: self._test_via_sdk(api_key))
            if sdk_result is not None:
                logger.info("OpenAI test_connection: SDK succeeded in %.1f ms", ms)
                return ConfigTestResult(success=True, message="Connected successfully", latency_ms=ms)
        except Exception as exc:
            logger.warning("OpenAI test_connection: SDK attempt failed (%s), falling back to HTTP", exc)

        # HTTP fallback
        logger.info("OpenAI test_connection: attempting via HTTP fallback (base_url=%s)", self._base_url())
        try:
            result, ms = self._timed(lambda: self._test_via_http(api_key))
            if result[0]:
                logger.info("OpenAI test_connection: HTTP fallback succeeded in %.1f ms", ms)
            else:
                logger.warning("OpenAI test_connection: HTTP fallback failed – %s", result[1])
            return ConfigTestResult(success=result[0], message=result[1], detail=result[2], latency_ms=ms)
        except Exception as exc:
            logger.exception("OpenAI test_connection: unexpected error during HTTP fallback")
            return ConfigTestResult(success=False, message="Connection failed", detail=str(exc))

    def _test_via_sdk(self, api_key: str) -> Any:
        from openai import OpenAI  # type: ignore[import]
        logger.debug("OpenAI _test_via_sdk: initialising OpenAI client")
        client = OpenAI(api_key=api_key, base_url=self._base_url())
        models = client.models.list()
        return models

    def _test_via_http(self, api_key: str) -> tuple[bool, str, str | None]:
        url = f"{self._base_url()}/models"
        logger.debug("OpenAI _test_via_http: GET %s", url)
        req = urllib.request.Request(
            url, headers={"Authorization": f"Bearer {api_key}"}
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    return True, "Connected successfully (HTTP)", None
                logger.warning("OpenAI _test_via_http: unexpected HTTP %s from %s", resp.status, url)
                return False, f"HTTP {resp.status}", None
        except urllib.error.HTTPError as exc:
            logger.warning("OpenAI _test_via_http: HTTP error %s %s from %s", exc.code, exc.reason, url)
            return False, f"HTTP {exc.code}", exc.reason
        except Exception as exc:
            logger.exception("OpenAI _test_via_http: unexpected error connecting to %s", url)
            return False, "Connection failed (HTTP)", str(exc)

    # ── fetch_models ──────────────────────────────────────────────────────────

    def fetch_models(self) -> FetchModelsResult:
        api_key = self._api_key()
        if not api_key:
            logger.warning("OpenAI fetch_models: 'api_key' property is missing")
            return FetchModelsResult(
                success=False,
                provider_slug="openai",
                message="'api_key' property is required for OpenAI",
            )

        logger.info("OpenAI fetch_models: attempting via SDK (base_url=%s)", self._base_url())
        try:
            models = self._fetch_via_sdk(api_key)
            if models is not None:
                logger.info("OpenAI fetch_models: SDK returned %d embedding model(s)", len(models))
                return FetchModelsResult(
                    success=True, provider_slug="openai",
                    models=models, message=f"Fetched {len(models)} embedding model(s)",
                )
        except Exception as exc:
            logger.warning("OpenAI fetch_models: SDK attempt failed (%s), falling back to HTTP", exc)

        logger.info("OpenAI fetch_models: attempting via HTTP fallback")
        return self._fetch_via_http(api_key)

    def _fetch_via_sdk(self, api_key: str) -> list[EmbeddingModel] | None:
        from openai import OpenAI  # type: ignore[import]
        logger.debug("OpenAI _fetch_via_sdk: initialising OpenAI client")
        client = OpenAI(api_key=api_key, base_url=self._base_url())
        raw = client.models.list()
        results = [
            EmbeddingModel(id=m.id, display_name=m.id)
            for m in raw.data
            if _is_embedding_model(m.id)
        ]
        logger.debug("OpenAI _fetch_via_sdk: filtered %d embedding models from %d total", len(results), len(raw.data))
        return results

    def _fetch_via_http(self, api_key: str) -> FetchModelsResult:
        url = f"{self._base_url()}/models"
        logger.debug("OpenAI _fetch_via_http: GET %s", url)
        req = urllib.request.Request(
            url, headers={"Authorization": f"Bearer {api_key}"}
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            models = [
                EmbeddingModel(id=m["id"], display_name=m["id"])
                for m in data.get("data", [])
                if _is_embedding_model(m.get("id", ""))
            ]
            logger.info("OpenAI _fetch_via_http: returned %d embedding model(s)", len(models))
            return FetchModelsResult(
                success=True, provider_slug="openai",
                models=models, message=f"Fetched {len(models)} embedding model(s)",
            )
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")
            logger.warning("OpenAI _fetch_via_http: HTTP error %s from %s – %s", exc.code, url, body[:200])
            return FetchModelsResult(
                success=False, provider_slug="openai",
                message="Failed to fetch models", detail=f"HTTP {exc.code}: {body[:200]}",
            )
        except Exception as exc:
            logger.exception("OpenAI _fetch_via_http: unexpected error fetching from %s", url)
            return FetchModelsResult(
                success=False, provider_slug="openai",
                message="Failed to fetch models", detail=str(exc),
            )
