"""
Unit tests for the embedding provider configuration feature:
  - EmbeddingService (business logic, secret masking, validation)
  - EmbeddingProviderFactory (slug routing)
  - Individual provider validation (missing required properties)
  - _mask_secrets helper
  - _validate_properties helper
"""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.embedding import EmbeddingProvider, TenantEmbeddingConfig
from app.models.user import User
from app.models.vectordb import VectorDbEnv
from app.providers.factory import EmbeddingProviderFactory
from app.providers.gemini_provider import GeminiProvider
from app.providers.ollama_provider import OllamaProvider
from app.providers.openai_provider import OpenAIProvider
from app.schemas.embedding import (
    ConfigTestResult,
    CreateEmbeddingConfigRequest,
    FetchModelsResult,
    UpdateEmbeddingConfigRequest,
)
from app.services.embedding_service import EmbeddingService, _mask_secrets


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> datetime.datetime:
    return datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)


def _make_user(**kw) -> MagicMock:
    defaults = dict(id=1, email="admin@acme.com", tenant_id="tenant-uuid", is_active=True)
    defaults.update(kw)
    u = MagicMock(spec=User)
    for k, v in defaults.items():
        setattr(u, k, v)
    return u


def _make_provider(
    slug: str = "openai",
    display_name: str = "OpenAI",
    props: list[dict] | None = None,
) -> MagicMock:
    if props is None:
        props = [
            {"name": "api_key", "label": "API Key", "type": "password", "required": True, "secret": True},
            {"name": "base_url", "label": "Base URL", "type": "string", "required": False, "secret": False},
        ]
    p = MagicMock(spec=EmbeddingProvider)
    p.id = 1
    p.slug = slug
    p.display_name = display_name
    p.description = f"{display_name} embedding provider"
    p.models_url = "https://api.openai.com/v1/models"
    p.property_schema = props
    return p


def _make_config(
    provider: MagicMock | None = None,
    properties: dict | None = None,
    environment: VectorDbEnv = VectorDbEnv.DEV,
) -> MagicMock:
    if provider is None:
        provider = _make_provider()
    if properties is None:
        properties = {"api_key": "sk-secret", "base_url": "https://api.openai.com/v1"}
    cfg = MagicMock(spec=TenantEmbeddingConfig)
    cfg.id = "cfg-uuid-1234"
    cfg.tenant_id = "tenant-uuid"
    cfg.created_by_user_id = 1
    cfg.provider_id = provider.id
    cfg.provider = provider
    cfg.name = "My OpenAI Config"
    cfg.environment = environment
    cfg.properties = properties
    cfg.created_at = _now()
    cfg.updated_at = _now()
    return cfg


@pytest.fixture()
def repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def service(repo: AsyncMock) -> EmbeddingService:
    return EmbeddingService(repo)


# ── _mask_secrets ─────────────────────────────────────────────────────────────

def test_mask_secrets_replaces_secret_values():
    schema = [
        {"name": "base_url", "secret": False},
        {"name": "api_key", "secret": True},
    ]
    props = {"base_url": "https://api.openai.com/v1", "api_key": "sk-realkey"}
    result = _mask_secrets(props, schema)
    assert result["base_url"] == "https://api.openai.com/v1"
    assert result["api_key"] == "***"


def test_mask_secrets_falsy_secret_not_masked():
    schema = [{"name": "api_key", "secret": True}]
    props = {"api_key": ""}
    result = _mask_secrets(props, schema)
    assert result["api_key"] == ""  # empty string stays as-is


def test_mask_secrets_non_secret_untouched():
    schema = [{"name": "base_url", "secret": False}]
    props = {"base_url": "http://localhost:11434"}
    result = _mask_secrets(props, schema)
    assert result["base_url"] == "http://localhost:11434"


def test_mask_secrets_returns_copy():
    schema = [{"name": "api_key", "secret": True}]
    original = {"api_key": "secret"}
    _mask_secrets(original, schema)
    assert original["api_key"] == "secret"  # original unchanged


# ── _validate_properties ─────────────────────────────────────────────────────

def test_validate_properties_raises_422_on_missing(service):
    provider = _make_provider(props=[
        {"name": "api_key", "required": True, "secret": True},
    ])
    with pytest.raises(HTTPException) as exc_info:
        service._validate_properties({}, provider)
    assert exc_info.value.status_code == 422
    assert "api_key" in exc_info.value.detail


def test_validate_properties_passes_when_all_required_present(service):
    provider = _make_provider(props=[
        {"name": "api_key", "required": True, "secret": True},
    ])
    service._validate_properties({"api_key": "sk-abc"}, provider)  # no exception


def test_validate_properties_optional_missing_is_ok(service):
    provider = _make_provider(props=[
        {"name": "api_key", "required": True, "secret": True},
        {"name": "base_url", "required": False, "secret": False},
    ])
    service._validate_properties({"api_key": "sk-abc"}, provider)  # no exception


def test_validate_properties_false_value_not_treated_as_missing(service):
    """Boolean False should NOT be treated as a missing required value."""
    provider = _make_provider(props=[
        {"name": "filter_embedding", "required": True, "secret": False},
    ])
    service._validate_properties({"filter_embedding": False}, provider)  # no exception


# ── EmbeddingService.list_providers ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_providers_returns_all(service, repo):
    p1 = _make_provider("openai", "OpenAI")
    p2 = _make_provider("ollama", "Ollama")
    repo.list_providers.return_value = [p1, p2]

    results = await service.list_providers()

    repo.list_providers.assert_awaited_once()
    assert len(results) == 2
    assert {r.slug for r in results} == {"openai", "ollama"}


@pytest.mark.asyncio
async def test_get_provider_not_found_raises_404(service, repo):
    repo.get_provider_by_id.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        await service.get_provider(999)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_provider_returns_data(service, repo):
    repo.get_provider_by_id.return_value = _make_provider("gemini", "Google Gemini")
    result = await service.get_provider(3)
    assert result.slug == "gemini"


# ── EmbeddingService.create_config ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_config_unknown_provider_raises_400(service, repo):
    repo.get_provider_by_slug.return_value = None
    payload = CreateEmbeddingConfigRequest(
        provider_slug="nonexistent", name="Test",
        environment=VectorDbEnv.DEV, properties={},
    )
    with pytest.raises(HTTPException) as exc_info:
        await service.create_config(payload, _make_user())
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_create_config_missing_required_raises_422(service, repo):
    provider = _make_provider(props=[{"name": "api_key", "required": True, "secret": True}])
    repo.get_provider_by_slug.return_value = provider
    payload = CreateEmbeddingConfigRequest(
        provider_slug="openai", name="Test",
        environment=VectorDbEnv.DEV, properties={},  # api_key missing
    )
    with pytest.raises(HTTPException) as exc_info:
        await service.create_config(payload, _make_user())
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_create_config_success(service, repo):
    provider = _make_provider(props=[{"name": "api_key", "required": True, "secret": True}])
    cfg = _make_config(provider=provider, properties={"api_key": "sk-abc"})
    repo.get_provider_by_slug.return_value = provider
    repo.create_config.return_value = cfg

    payload = CreateEmbeddingConfigRequest(
        provider_slug="openai", name="My OpenAI Config",
        environment=VectorDbEnv.DEV, properties={"api_key": "sk-abc"},
    )
    result = await service.create_config(payload, _make_user())

    repo.create_config.assert_awaited_once()
    assert result.name == "My OpenAI Config"
    assert result.provider_slug == "openai"
    assert result.properties["api_key"] == "***"  # secret is masked


# ── EmbeddingService.get_config ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_config_not_found_raises_404(service, repo):
    repo.get_config.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        await service.get_config("bad-id", "tenant-uuid")
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_config_masks_secrets(service, repo):
    provider = _make_provider(props=[
        {"name": "api_key", "required": True, "secret": True},
        {"name": "base_url", "required": False, "secret": False},
    ])
    cfg = _make_config(provider=provider, properties={"api_key": "sk-real", "base_url": "https://api.openai.com"})
    repo.get_config.return_value = cfg

    result = await service.get_config("cfg-uuid-1234", "tenant-uuid")

    assert result.properties["api_key"] == "***"
    assert result.properties["base_url"] == "https://api.openai.com"


# ── EmbeddingService.update_config ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_config_not_found_raises_404(service, repo):
    repo.get_config.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        await service.update_config("bad-id", UpdateEmbeddingConfigRequest(), "tenant-uuid")
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_update_config_validates_new_properties(service, repo):
    provider = _make_provider(props=[{"name": "api_key", "required": True, "secret": True}])
    cfg = _make_config(provider=provider)
    repo.get_config.return_value = cfg

    with pytest.raises(HTTPException) as exc_info:
        await service.update_config(
            "cfg-uuid-1234",
            UpdateEmbeddingConfigRequest(properties={"api_key": None}),
            "tenant-uuid",
        )
    assert exc_info.value.status_code == 422


# ── EmbeddingService.delete_config ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_config_not_found_raises_404(service, repo):
    repo.get_config.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        await service.delete_config("bad-id", "tenant-uuid")
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_config_calls_repo(service, repo):
    cfg = _make_config()
    repo.get_config.return_value = cfg
    await service.delete_config("cfg-uuid-1234", "tenant-uuid")
    repo.delete_config.assert_awaited_once_with(cfg)


# ── EmbeddingService.test_config ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_test_config_not_found_raises_404(service, repo):
    repo.get_config.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        await service.test_config("bad-id", "tenant-uuid")
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_test_config_unknown_slug_returns_failure(service, repo):
    provider = _make_provider(slug="unknown_provider")
    cfg = _make_config(provider=provider)
    repo.get_config.return_value = cfg

    result = await service.test_config("cfg-uuid-1234", "tenant-uuid")
    assert result.success is False


@pytest.mark.asyncio
async def test_test_config_calls_provider(service, repo):
    provider = _make_provider(slug="openai")
    cfg = _make_config(provider=provider, properties={"api_key": "sk-abc"})
    repo.get_config.return_value = cfg

    mock_result = ConfigTestResult(success=True, message="OK")
    mock_impl = MagicMock()
    mock_impl.test_connection.return_value = mock_result

    with patch("app.services.embedding_service.EmbeddingProviderFactory.get", return_value=mock_impl):
        result = await service.test_config("cfg-uuid-1234", "tenant-uuid")

    assert result.success is True
    mock_impl.test_connection.assert_called_once()


# ── EmbeddingService.fetch_models ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_models_not_found_raises_404(service, repo):
    repo.get_config.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        await service.fetch_models("bad-id", "tenant-uuid")
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_fetch_models_calls_provider(service, repo):
    from app.schemas.embedding import EmbeddingModel
    provider = _make_provider(slug="openai")
    cfg = _make_config(provider=provider, properties={"api_key": "sk-abc"})
    repo.get_config.return_value = cfg

    mock_result = FetchModelsResult(
        success=True, provider_slug="openai",
        models=[EmbeddingModel(id="text-embedding-3-small")],
        message="OK",
    )
    mock_impl = MagicMock()
    mock_impl.fetch_models.return_value = mock_result

    with patch("app.services.embedding_service.EmbeddingProviderFactory.get", return_value=mock_impl):
        result = await service.fetch_models("cfg-uuid-1234", "tenant-uuid")

    assert result.success is True
    assert len(result.models) == 1
    assert result.models[0].id == "text-embedding-3-small"
    mock_impl.fetch_models.assert_called_once()


@pytest.mark.asyncio
async def test_fetch_models_unknown_slug_returns_failure(service, repo):
    provider = _make_provider(slug="unknown_provider")
    cfg = _make_config(provider=provider)
    repo.get_config.return_value = cfg

    result = await service.fetch_models("cfg-uuid-1234", "tenant-uuid")
    assert result.success is False


# ── list_configs filtering ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_configs_unknown_provider_raises_400(service, repo):
    repo.get_provider_by_slug.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        await service.list_configs("tenant-uuid", provider_slug="nonexistent")
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_list_configs_passes_provider_id_to_repo(service, repo):
    provider = _make_provider("openai")
    provider.id = 7
    repo.get_provider_by_slug.return_value = provider
    repo.list_configs.return_value = []

    await service.list_configs("tenant-uuid", provider_slug="openai")
    repo.list_configs.assert_awaited_once_with("tenant-uuid", None, 7)


@pytest.mark.asyncio
async def test_list_configs_no_filter(service, repo):
    cfg = _make_config()
    repo.list_configs.return_value = [cfg]

    results = await service.list_configs("tenant-uuid")
    repo.list_configs.assert_awaited_once_with("tenant-uuid", None, None)
    assert len(results) == 1


# ── EmbeddingProviderFactory ──────────────────────────────────────────────────

def test_factory_returns_openai_provider():
    p = EmbeddingProviderFactory.get("openai", {"api_key": "key"})
    assert isinstance(p, OpenAIProvider)


def test_factory_returns_ollama_provider():
    p = EmbeddingProviderFactory.get("ollama", {"base_url": "http://localhost:11434"})
    assert isinstance(p, OllamaProvider)


def test_factory_returns_gemini_provider():
    p = EmbeddingProviderFactory.get("gemini", {"api_key": "keykey"})
    assert isinstance(p, GeminiProvider)


def test_factory_unknown_slug_raises_value_error():
    with pytest.raises(ValueError, match="Unsupported embedding provider"):
        EmbeddingProviderFactory.get("cohere", {})


def test_factory_supported_slugs():
    assert set(EmbeddingProviderFactory.supported_slugs()) == {"openai", "ollama", "gemini"}


# ── OpenAIProvider ────────────────────────────────────────────────────────────

def test_openai_missing_api_key_returns_failure():
    p = OpenAIProvider({})
    result = p.test_connection()
    assert result.success is False
    assert "api_key" in (result.detail or "").lower()


def test_openai_fetch_models_missing_api_key():
    p = OpenAIProvider({})
    result = p.fetch_models()
    assert result.success is False
    assert "api_key" in result.message.lower()


def test_openai_invalid_key_test_fails():
    p = OpenAIProvider({"api_key": "sk-invalid-key-xyz"})
    result = p.test_connection()
    assert result.success is False


def test_openai_invalid_key_fetch_fails():
    p = OpenAIProvider({"api_key": "sk-invalid-key-xyz"})
    result = p.fetch_models()
    assert result.success is False


# ── OllamaProvider ────────────────────────────────────────────────────────────

def test_ollama_missing_base_url_returns_failure():
    p = OllamaProvider({})
    result = p.test_connection()
    assert result.success is False
    assert "base_url" in (result.detail or "").lower()


def test_ollama_fetch_models_missing_base_url():
    p = OllamaProvider({})
    result = p.fetch_models()
    assert result.success is False
    assert "base_url" in result.message.lower()


def test_ollama_unreachable_returns_failure():
    p = OllamaProvider({"base_url": "http://192.0.2.1:11434"})  # TEST-NET
    result = p.test_connection()
    assert result.success is False
    assert result.message


def test_ollama_filter_true_only_embeds(monkeypatch):
    """When filter_embedding=True, only models with embedding-related names appear."""
    import urllib.request

    mock_data = b'{"models": [{"name": "nomic-embed-text"}, {"name": "llama3.2"}, {"name": "all-minilm"}]}'

    class FakeResponse:
        def __init__(self):
            self.status = 200
        def read(self):
            return mock_data
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: FakeResponse())
    p = OllamaProvider({"base_url": "http://localhost:11434", "filter_embedding": True})
    result = p.fetch_models()
    assert result.success is True
    model_ids = [m.id for m in result.models]
    assert "nomic-embed-text" in model_ids
    assert "all-minilm" in model_ids
    assert "llama3.2" not in model_ids  # filtered out


def test_ollama_filter_false_returns_all(monkeypatch):
    import urllib.request

    mock_data = b'{"models": [{"name": "nomic-embed-text"}, {"name": "llama3.2"}]}'

    class FakeResponse:
        def __init__(self):
            self.status = 200
        def read(self):
            return mock_data
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: FakeResponse())
    p = OllamaProvider({"base_url": "http://localhost:11434", "filter_embedding": False})
    result = p.fetch_models()
    assert result.success is True
    assert len(result.models) == 2


# ── GeminiProvider ────────────────────────────────────────────────────────────

def test_gemini_missing_api_key_returns_failure():
    p = GeminiProvider({})
    result = p.test_connection()
    assert result.success is False
    assert "api_key" in (result.detail or "").lower()


def test_gemini_fetch_models_missing_api_key():
    p = GeminiProvider({})
    result = p.fetch_models()
    assert result.success is False
    assert "api_key" in result.message.lower()


def test_gemini_invalid_key_test_fails():
    p = GeminiProvider({"api_key": "invalid-gemini-key"})
    result = p.test_connection()
    assert result.success is False


def test_gemini_fetch_models_filters_by_capability(monkeypatch):
    """Only models with embedContent/batchEmbedContents support appear."""
    import urllib.request, json

    mock_data = json.dumps({
        "models": [
            {"name": "models/text-embedding-004", "displayName": "Text Embedding 004",
             "supportedGenerationMethods": ["embedContent", "batchEmbedContents"]},
            {"name": "models/gemini-1.5-pro", "displayName": "Gemini 1.5 Pro",
             "supportedGenerationMethods": ["generateContent"]},
        ]
    }).encode()

    class FakeResponse:
        def __init__(self):
            self.status = 200
        def read(self):
            return mock_data
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: FakeResponse())
    p = GeminiProvider({"api_key": "fake-key"})
    result = p.fetch_models()
    assert result.success is True
    model_ids = [m.id for m in result.models]
    assert "text-embedding-004" in model_ids
    assert "gemini-1.5-pro" not in model_ids
