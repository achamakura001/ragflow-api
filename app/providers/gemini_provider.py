"""
Google Gemini embedding provider.

Required property : ``api_key``  (secret)
Optional property : ``base_url`` (default: https://generativelanguage.googleapis.com/v1beta)

Calls GET {base_url}/models?key={api_key} and filters models that support
the "embedContent" or "batchEmbedContents" method.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from app.providers import BaseEmbeddingProvider
from app.schemas.embedding import ConfigTestResult, EmbeddingModel, FetchModelsResult

logger = logging.getLogger(__name__)

_DEFAULT_BASE = "https://generativelanguage.googleapis.com/v1beta"
_EMBED_METHODS = {"embedContent", "batchEmbedContents"}


def _supports_embedding(model: dict) -> bool:
    supported = set(model.get("supportedGenerationMethods", []))
    # Also match on name
    name = model.get("name", "").lower()
    return bool(supported & _EMBED_METHODS) or "embed" in name


class GeminiProvider(BaseEmbeddingProvider):
    """Google Gemini embedding provider."""

    def _api_key(self) -> str | None:
        v = str(self._props.get("api_key", "")).strip()
        return v or None

    def _base_url(self) -> str:
        return str(self._props.get("base_url", _DEFAULT_BASE)).rstrip("/")

    # ── test_connection ───────────────────────────────────────────────────────

    def test_connection(self) -> ConfigTestResult:
        api_key = self._api_key()
        if not api_key:
            logger.warning("Gemini test_connection: 'api_key' property is missing")
            return ConfigTestResult(
                success=False,
                message="Connection failed",
                detail="'api_key' property is required for Gemini",
            )

        url = f"{self._base_url()}/models?key=<redacted>&pageSize=1"
        logger.info("Gemini test_connection: GET %s", url)
        probe_url = f"{self._base_url()}/models?key={api_key}&pageSize=1"
        try:
            def _do():
                with urllib.request.urlopen(probe_url, timeout=10) as r:
                    return r.status
            status, ms = self._timed(_do)
            if status == 200:
                logger.info("Gemini test_connection: success (HTTP 200) in %.1f ms", ms)
                return ConfigTestResult(success=True, message="Connected successfully", latency_ms=ms)
            logger.warning("Gemini test_connection: unexpected HTTP %s", status)
            return ConfigTestResult(success=False, message=f"Unexpected HTTP {status}", latency_ms=ms)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")
            logger.warning("Gemini test_connection: HTTP error %s – %s", exc.code, body[:200])
            return ConfigTestResult(
                success=False, message="Connection failed",
                detail=f"HTTP {exc.code}: {body[:200]}",
            )
        except Exception as exc:
            logger.exception("Gemini test_connection: unexpected error")
            return ConfigTestResult(success=False, message="Connection failed", detail=str(exc))

    # ── fetch_models ──────────────────────────────────────────────────────────

    def fetch_models(self) -> FetchModelsResult:
        api_key = self._api_key()
        if not api_key:
            logger.warning("Gemini fetch_models: 'api_key' property is missing")
            return FetchModelsResult(
                success=False, provider_slug="gemini",
                message="'api_key' property is required for Gemini",
            )

        models: list[EmbeddingModel] = []
        page_token: str | None = None
        page_num = 0

        while True:
            page_num += 1
            url = f"{self._base_url()}/models?key={api_key}&pageSize=100"
            if page_token:
                url += f"&pageToken={page_token}"
            safe_url = url.replace(api_key, "<redacted>")
            logger.info("Gemini fetch_models: GET %s (page %d)", safe_url, page_num)

            try:
                with urllib.request.urlopen(url, timeout=10) as resp:
                    data = json.loads(resp.read())
            except urllib.error.HTTPError as exc:
                body = exc.read().decode(errors="replace")
                logger.warning("Gemini fetch_models: HTTP error %s on page %d – %s", exc.code, page_num, body[:200])
                return FetchModelsResult(
                    success=False, provider_slug="gemini",
                    message="Failed to fetch models", detail=f"HTTP {exc.code}: {body[:200]}",
                )
            except Exception as exc:
                logger.exception("Gemini fetch_models: unexpected error fetching page %d", page_num)
                return FetchModelsResult(
                    success=False, provider_slug="gemini",
                    message="Failed to fetch models", detail=str(exc),
                )

            for m in data.get("models", []):
                if _supports_embedding(m):
                    model_id = m.get("name", "").split("/")[-1]  # strip "models/" prefix
                    models.append(EmbeddingModel(
                        id=model_id,
                        display_name=m.get("displayName", model_id),
                        description=m.get("description"),
                    ))

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        logger.info("Gemini fetch_models: completed – %d embedding model(s) across %d page(s)", len(models), page_num)
        return FetchModelsResult(
            success=True, provider_slug="gemini",
            models=models, message=f"Fetched {len(models)} embedding model(s)",
        )
