"""
Unit tests for the vector DB feature:
  - VectorDbService (business logic and secret masking)
  - ConnectorFactory (slug routing)
  - Individual connector validation (missing required props)
  - _mask_secrets helper
  - _validate_properties helper
"""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.connectors.factory import ConnectorFactory
from app.connectors.milvus_connector import MilvusConnector
from app.connectors.pinecone_connector import PineconeConnector
from app.connectors.qdrant_connector import QdrantConnector
from app.models.vectordb import VectorDbConnection, VectorDbEnv, VectorDbType
from app.models.user import User
from app.schemas.vectordb import (
    ConnectionTestResult,
    CreateConnectionRequest,
    UpdateConnectionRequest,
)
from app.services.vectordb_service import VectorDbService, _mask_secrets


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> datetime.datetime:
    return datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)


def _make_user(**kw) -> MagicMock:
    defaults = dict(
        id=1,
        email="admin@acme.com",
        first_name="Admin",
        last_name="User",
        tenant_id="tenant-uuid",
        is_active=True,
    )
    defaults.update(kw)
    u = MagicMock(spec=User)
    for k, v in defaults.items():
        setattr(u, k, v)
    return u


def _make_db_type(
    slug: str = "qdrant",
    display_name: str = "Qdrant",
    props: list[dict] | None = None,
) -> MagicMock:
    if props is None:
        props = [
            {"name": "url", "label": "URL", "type": "string", "required": True, "secret": False},
            {"name": "api_key", "label": "API Key", "type": "password", "required": False, "secret": True},
        ]
    t = MagicMock(spec=VectorDbType)
    t.id = 1
    t.slug = slug
    t.display_name = display_name
    t.description = "A vector database"
    t.property_schema = props
    return t


def _make_connection(
    db_type: MagicMock | None = None,
    properties: dict | None = None,
    environment: VectorDbEnv = VectorDbEnv.DEV,
) -> MagicMock:
    if db_type is None:
        db_type = _make_db_type()
    if properties is None:
        properties = {"url": "http://localhost:6333", "api_key": "secret123"}
    conn = MagicMock(spec=VectorDbConnection)
    conn.id = "conn-uuid-1234"
    conn.tenant_id = "tenant-uuid"
    conn.created_by_user_id = 1
    conn.type_id = db_type.id
    conn.db_type = db_type
    conn.name = "My Qdrant"
    conn.environment = environment
    conn.properties = properties
    conn.created_at = _now()
    conn.updated_at = _now()
    return conn


@pytest.fixture()
def repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def service(repo: AsyncMock) -> VectorDbService:
    return VectorDbService(repo)


# ── _mask_secrets ─────────────────────────────────────────────────────────────


def test_mask_secrets_replaces_secret_values():
    schema = [
        {"name": "url", "secret": False},
        {"name": "api_key", "secret": True},
        {"name": "password", "secret": True},
    ]
    props = {"url": "http://localhost:6333", "api_key": "sk-abc123", "password": "supersecret"}
    result = _mask_secrets(props, schema)
    assert result["url"] == "http://localhost:6333"
    assert result["api_key"] == "***"
    assert result["password"] == "***"


def test_mask_secrets_empty_secret_not_masked():
    """A falsy secret value (empty string, None) stays as-is rather than becoming '***'."""
    schema = [{"name": "api_key", "secret": True}]
    props = {"api_key": ""}
    result = _mask_secrets(props, schema)
    assert result["api_key"] == ""


def test_mask_secrets_non_secret_fields_untouched():
    schema = [{"name": "host", "secret": False}]
    props = {"host": "localhost"}
    result = _mask_secrets(props, schema)
    assert result["host"] == "localhost"


def test_mask_secrets_returns_copy_not_mutate():
    schema = [{"name": "token", "secret": True}]
    props = {"token": "abc"}
    result = _mask_secrets(props, schema)
    assert props["token"] == "abc"  # original unchanged


# ── _validate_properties ─────────────────────────────────────────────────────

def test_validate_properties_raises_422_when_required_missing(service):
    db_type = _make_db_type(props=[
        {"name": "url", "required": True, "secret": False},
        {"name": "api_key", "required": False, "secret": True},
    ])
    with pytest.raises(HTTPException) as exc_info:
        service._validate_properties({}, db_type)
    assert exc_info.value.status_code == 422
    assert "url" in exc_info.value.detail


def test_validate_properties_passes_with_all_required(service):
    db_type = _make_db_type(props=[
        {"name": "url", "required": True, "secret": False},
    ])
    # Should not raise
    service._validate_properties({"url": "http://localhost:6333"}, db_type)


def test_validate_properties_optional_missing_is_ok(service):
    db_type = _make_db_type(props=[
        {"name": "url", "required": True, "secret": False},
        {"name": "api_key", "required": False, "secret": True},
    ])
    # Optional field absent – should not raise
    service._validate_properties({"url": "http://qd"}, db_type)


# ── VectorDbService.list_supported_types ─────────────────────────────────────

@pytest.mark.asyncio
async def test_list_supported_types_returns_all(service, repo):
    t1 = _make_db_type("qdrant", "Qdrant")
    t2 = _make_db_type("pinecone", "Pinecone")
    repo.list_types.return_value = [t1, t2]

    results = await service.list_supported_types()

    repo.list_types.assert_awaited_once()
    assert len(results) == 2
    slugs = {r.slug for r in results}
    assert slugs == {"qdrant", "pinecone"}


@pytest.mark.asyncio
async def test_get_type_not_found_raises_404(service, repo):
    repo.get_type_by_id.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        await service.get_type(999)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_type_returns_type(service, repo):
    repo.get_type_by_id.return_value = _make_db_type()
    result = await service.get_type(1)
    assert result.slug == "qdrant"


# ── VectorDbService.create_connection ────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_connection_unknown_type_raises_400(service, repo):
    repo.get_type_by_slug.return_value = None
    payload = CreateConnectionRequest(
        type_slug="nonexistent",
        name="Test",
        environment=VectorDbEnv.DEV,
        properties={},
    )
    with pytest.raises(HTTPException) as exc_info:
        await service.create_connection(payload, _make_user())
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_create_connection_missing_required_raises_422(service, repo):
    db_type = _make_db_type(props=[
        {"name": "url", "required": True, "secret": False},
    ])
    repo.get_type_by_slug.return_value = db_type

    payload = CreateConnectionRequest(
        type_slug="qdrant",
        name="Test",
        environment=VectorDbEnv.DEV,
        properties={},  # url missing
    )
    with pytest.raises(HTTPException) as exc_info:
        await service.create_connection(payload, _make_user())
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_create_connection_success(service, repo):
    db_type = _make_db_type(props=[
        {"name": "url", "required": True, "secret": False},
    ])
    conn = _make_connection(db_type=db_type, properties={"url": "http://localhost:6333"})
    repo.get_type_by_slug.return_value = db_type
    repo.create_connection.return_value = conn

    payload = CreateConnectionRequest(
        type_slug="qdrant",
        name="My Qdrant",
        environment=VectorDbEnv.DEV,
        properties={"url": "http://localhost:6333"},
    )
    result = await service.create_connection(payload, _make_user())

    repo.create_connection.assert_awaited_once()
    assert result.name == "My Qdrant"
    assert result.type_slug == "qdrant"


# ── VectorDbService.get_connection ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_connection_not_found_raises_404(service, repo):
    repo.get_connection.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        await service.get_connection("some-id", "tenant-uuid")
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_connection_masks_secrets(service, repo):
    db_type = _make_db_type(props=[
        {"name": "url", "required": True, "secret": False},
        {"name": "api_key", "required": False, "secret": True},
    ])
    conn = _make_connection(
        db_type=db_type,
        properties={"url": "http://localhost", "api_key": "real-secret"},
    )
    repo.get_connection.return_value = conn

    result = await service.get_connection("conn-uuid-1234", "tenant-uuid")

    assert result.properties["url"] == "http://localhost"
    assert result.properties["api_key"] == "***"


# ── VectorDbService.delete_connection ────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_connection_not_found_raises_404(service, repo):
    repo.get_connection.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        await service.delete_connection("bad-id", "tenant-uuid")
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_connection_calls_repo(service, repo):
    conn = _make_connection()
    repo.get_connection.return_value = conn
    await service.delete_connection("conn-uuid-1234", "tenant-uuid")
    repo.delete_connection.assert_awaited_once_with(conn)


# ── VectorDbService.test_connection ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_test_connection_not_found_raises_404(service, repo):
    repo.get_connection.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        await service.test_connection("bad-id", "tenant-uuid")
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_test_connection_unknown_slug_returns_failure(service, repo):
    db_type = _make_db_type(slug="unknown_db")
    conn = _make_connection(db_type=db_type)
    repo.get_connection.return_value = conn

    result = await service.test_connection("conn-uuid-1234", "tenant-uuid")

    assert result.success is False


@pytest.mark.asyncio
async def test_test_connection_uses_connector(service, repo):
    """ConnectorFactory.get is called with the right slug; its result is returned."""
    db_type = _make_db_type(slug="qdrant")
    conn = _make_connection(db_type=db_type, properties={"url": "http://qdrant"})
    repo.get_connection.return_value = conn

    mock_result = ConnectionTestResult(success=True, message="OK")
    mock_connector = MagicMock()
    mock_connector.test_connection.return_value = mock_result

    with patch("app.services.vectordb_service.ConnectorFactory.get", return_value=mock_connector):
        result = await service.test_connection("conn-uuid-1234", "tenant-uuid")

    assert result.success is True
    mock_connector.test_connection.assert_called_once()


# ── ConnectorFactory ──────────────────────────────────────────────────────────

def test_factory_returns_qdrant_connector():
    connector = ConnectorFactory.get("qdrant", {"url": "http://localhost:6333"})
    assert isinstance(connector, QdrantConnector)


def test_factory_returns_pinecone_connector():
    connector = ConnectorFactory.get("pinecone", {"api_key": "key"})
    assert isinstance(connector, PineconeConnector)


def test_factory_returns_milvus_connector():
    connector = ConnectorFactory.get("milvus", {"host": "localhost"})
    assert isinstance(connector, MilvusConnector)


def test_factory_unknown_slug_raises_value_error():
    with pytest.raises(ValueError, match="Unsupported vector DB type"):
        ConnectorFactory.get("chromadb", {})


def test_factory_supported_slugs():
    slugs = ConnectorFactory.supported_slugs()
    assert set(slugs) == {"qdrant", "pinecone", "milvus"}


# ── QdrantConnector ───────────────────────────────────────────────────────────

def test_qdrant_connector_missing_url_returns_failure():
    connector = QdrantConnector({})
    result = connector.test_connection()
    assert result.success is False
    assert "url" in (result.detail or "").lower()


def test_qdrant_connector_with_invalid_url_returns_failure():
    connector = QdrantConnector({"url": "http://192.0.2.1:9999"})  # TEST-NET – unreachable
    result = connector.test_connection()
    assert result.success is False
    assert result.message  # some error message present


# ── PineconeConnector ─────────────────────────────────────────────────────────

def test_pinecone_connector_missing_api_key_returns_failure():
    connector = PineconeConnector({})
    result = connector.test_connection()
    assert result.success is False
    assert "api_key" in (result.detail or "").lower()


def test_pinecone_connector_invalid_key_returns_failure():
    connector = PineconeConnector({"api_key": "bad-key"})
    result = connector.test_connection()
    assert result.success is False


# ── MilvusConnector ───────────────────────────────────────────────────────────

def test_milvus_connector_missing_host_returns_failure():
    connector = MilvusConnector({})
    result = connector.test_connection()
    assert result.success is False
    assert "host" in (result.detail or "").lower()


def test_milvus_connector_unreachable_host_returns_failure():
    connector = MilvusConnector({"host": "192.0.2.1", "port": 19530})  # TEST-NET, unreachable
    result = connector.test_connection()
    assert result.success is False
    assert result.message  # some error message present


# ── list_connections filtering ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_connections_unknown_type_slug_raises_400(service, repo):
    repo.get_type_by_slug.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        await service.list_connections("tenant-uuid", type_slug="nonexistent")
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_list_connections_passes_type_id_to_repo(service, repo):
    db_type = _make_db_type("qdrant")
    db_type.id = 42
    repo.get_type_by_slug.return_value = db_type
    repo.list_connections.return_value = []

    await service.list_connections("tenant-uuid", type_slug="qdrant")

    repo.list_connections.assert_awaited_once_with("tenant-uuid", None, 42)


@pytest.mark.asyncio
async def test_list_connections_no_filter(service, repo):
    conn = _make_connection()
    repo.list_connections.return_value = [conn]

    results = await service.list_connections("tenant-uuid")

    repo.list_connections.assert_awaited_once_with("tenant-uuid", None, None)
    assert len(results) == 1
