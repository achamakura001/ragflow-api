"""
Factory that maps provider slugs to concrete provider classes.

Usage:
    provider = EmbeddingProviderFactory.get("openai", {"api_key": "sk-…"})
    result = provider.fetch_models()
"""

from __future__ import annotations

from typing import Any

from app.providers import BaseEmbeddingProvider
from app.providers.gemini_provider import GeminiProvider
from app.providers.ollama_provider import OllamaProvider
from app.providers.openai_provider import OpenAIProvider


class EmbeddingProviderFactory:
    _REGISTRY: dict[str, type[BaseEmbeddingProvider]] = {
        "openai": OpenAIProvider,
        "ollama": OllamaProvider,
        "gemini": GeminiProvider,
    }

    @classmethod
    def get(cls, provider_slug: str, properties: dict[str, Any]) -> BaseEmbeddingProvider:
        """Return an instantiated provider for the given slug.

        Raises ValueError for unknown slugs.
        """
        klass = cls._REGISTRY.get(provider_slug.lower())
        if klass is None:
            raise ValueError(
                f"Unsupported embedding provider '{provider_slug}'. "
                f"Supported: {list(cls._REGISTRY)}"
            )
        return klass(properties)

    @classmethod
    def supported_slugs(cls) -> list[str]:
        return list(cls._REGISTRY)
