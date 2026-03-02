"""
Connector factory – maps a VectorDbType slug to the appropriate connector class.

Usage:
    connector = ConnectorFactory.get("qdrant", {"url": "http://localhost:6333"})
    result = connector.test_connection()
"""

from __future__ import annotations

from typing import Any

from app.connectors import BaseVectorConnector
from app.connectors.milvus_connector import MilvusConnector
from app.connectors.pinecone_connector import PineconeConnector
from app.connectors.qdrant_connector import QdrantConnector

_REGISTRY: dict[str, type[BaseVectorConnector]] = {
    "qdrant": QdrantConnector,
    "pinecone": PineconeConnector,
    "milvus": MilvusConnector,
}


class ConnectorFactory:
    @staticmethod
    def get(type_slug: str, properties: dict[str, Any]) -> BaseVectorConnector:
        """
        Return an instantiated connector for the given vector DB type slug.

        Raises ValueError for unknown slugs.
        """
        cls = _REGISTRY.get(type_slug.lower())
        if cls is None:
            supported = ", ".join(_REGISTRY)
            raise ValueError(
                f"Unsupported vector DB type '{type_slug}'. "
                f"Supported: {supported}"
            )
        return cls(properties)

    @staticmethod
    def supported_slugs() -> list[str]:
        return list(_REGISTRY.keys())
