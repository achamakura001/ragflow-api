"""add_vector_db_types_and_connections

Revision ID: f7090923539f
Revises: 2df1a31f28f1
Create Date: 2026-03-01 13:02:54.329793

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'f7090923539f'
down_revision: Union[str, Sequence[str], None] = '2df1a31f28f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_QDRANT_PROPS = [
    {
        "name": "url",
        "label": "URL",
        "type": "string",
        "required": True,
        "secret": False,
        "placeholder": "http://localhost:6333",
        "description": "Full HTTP URL of the Qdrant server",
        "default": None,
    },
    {
        "name": "api_key",
        "label": "API Key",
        "type": "password",
        "required": False,
        "secret": True,
        "placeholder": "",
        "description": "Optional API key for authenticated Qdrant Cloud instances",
        "default": None,
    },
    {
        "name": "grpc_port",
        "label": "gRPC Port",
        "type": "integer",
        "required": False,
        "secret": False,
        "placeholder": "6334",
        "description": "gRPC port (leave blank to use REST only)",
        "default": None,
    },
    {
        "name": "prefer_grpc",
        "label": "Prefer gRPC",
        "type": "boolean",
        "required": False,
        "secret": False,
        "placeholder": "",
        "description": "Use gRPC transport when available",
        "default": False,
    },
]

_PINECONE_PROPS = [
    {
        "name": "api_key",
        "label": "API Key",
        "type": "password",
        "required": True,
        "secret": True,
        "placeholder": "",
        "description": "Pinecone API key from your Pinecone console",
        "default": None,
    },
    {
        "name": "environment",
        "label": "Environment",
        "type": "string",
        "required": False,
        "secret": False,
        "placeholder": "us-east1-gcp",
        "description": "Pinecone environment (legacy; not needed for serverless)",
        "default": None,
    },
    {
        "name": "host",
        "label": "Index Host",
        "type": "string",
        "required": False,
        "secret": False,
        "placeholder": "https://my-index-xyz.svc.pinecone.io",
        "description": "Direct index host URL (serverless / dedicated pod)",
        "default": None,
    },
    {
        "name": "index_name",
        "label": "Index Name",
        "type": "string",
        "required": False,
        "secret": False,
        "placeholder": "my-index",
        "description": "Default index name to connect to",
        "default": None,
    },
    {
        "name": "namespace",
        "label": "Namespace",
        "type": "string",
        "required": False,
        "secret": False,
        "placeholder": "",
        "description": "Default namespace within the index",
        "default": None,
    },
]

_MILVUS_PROPS = [
    {
        "name": "host",
        "label": "Host",
        "type": "string",
        "required": True,
        "secret": False,
        "placeholder": "localhost",
        "description": "Milvus server hostname or IP address",
        "default": None,
    },
    {
        "name": "port",
        "label": "Port",
        "type": "integer",
        "required": False,
        "secret": False,
        "placeholder": "19530",
        "description": "Milvus server port",
        "default": 19530,
    },
    {
        "name": "user",
        "label": "Username",
        "type": "string",
        "required": False,
        "secret": False,
        "placeholder": "root",
        "description": "Milvus username (if authentication is enabled)",
        "default": None,
    },
    {
        "name": "password",
        "label": "Password",
        "type": "password",
        "required": False,
        "secret": True,
        "placeholder": "",
        "description": "Milvus password (if authentication is enabled)",
        "default": None,
    },
    {
        "name": "secure",
        "label": "TLS / Secure",
        "type": "boolean",
        "required": False,
        "secret": False,
        "placeholder": "",
        "description": "Use TLS encrypted connection",
        "default": False,
    },
    {
        "name": "db_name",
        "label": "Database",
        "type": "string",
        "required": False,
        "secret": False,
        "placeholder": "default",
        "description": "Milvus database name",
        "default": "default",
    },
]


def upgrade() -> None:
    """Create vector_db_types and vector_db_connections tables; drop legacy items table."""

    # ---------- vector_db_types (catalogue) ----------
    op.create_table(
        'vector_db_types',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('slug', sa.String(length=64), nullable=False),
        sa.Column('display_name', sa.String(length=128), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('property_schema', sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug'),
    )
    op.create_index(op.f('ix_vector_db_types_id'), 'vector_db_types', ['id'], unique=False)
    op.create_index(op.f('ix_vector_db_types_slug'), 'vector_db_types', ['slug'], unique=True)

    # ---------- seed supported types ----------
    vector_db_types_table = sa.table(
        'vector_db_types',
        sa.column('slug', sa.String),
        sa.column('display_name', sa.String),
        sa.column('description', sa.String),
        sa.column('property_schema', sa.JSON),
    )
    op.bulk_insert(
        vector_db_types_table,
        [
            {
                'slug': 'qdrant',
                'display_name': 'Qdrant',
                'description': 'Open-source vector database with REST and gRPC API support.',
                'property_schema': _QDRANT_PROPS,
            },
            {
                'slug': 'pinecone',
                'display_name': 'Pinecone',
                'description': 'Managed serverless vector database for production AI applications.',
                'property_schema': _PINECONE_PROPS,
            },
            {
                'slug': 'milvus',
                'display_name': 'Milvus',
                'description': 'Open-source, cloud-native vector database built for scalable similarity search.',
                'property_schema': _MILVUS_PROPS,
            },
        ],
    )

    # ---------- vector_db_connections (tenant-scoped) ----------
    op.create_table(
        'vector_db_connections',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('type_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column(
            'environment',
            sa.Enum('dev', 'qa', 'perf', 'prod', name='vectordbenv'),
            nullable=False,
        ),
        sa.Column('properties', sa.JSON(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(),
            nullable=False,
            server_default=sa.text('now()'),
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(),
            nullable=False,
            server_default=sa.text('now()'),
            onupdate=sa.text('now()'),
        ),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['type_id'], ['vector_db_types.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_vector_db_connections_id'),
        'vector_db_connections',
        ['id'],
        unique=False,
    )
    op.create_index(
        'ix_vdb_conn_tenant_env',
        'vector_db_connections',
        ['tenant_id', 'environment'],
        unique=False,
    )

    # ---------- drop legacy items table ----------
    try:
        op.drop_index(op.f('ix_items_id'), table_name='items')
    except Exception:
        pass
    try:
        op.drop_index(op.f('ix_items_title'), table_name='items')
    except Exception:
        pass
    try:
        op.drop_table('items')
    except Exception:
        pass


def downgrade() -> None:
    """Reverse: drop vector DB tables, restore items table."""

    op.drop_index('ix_vdb_conn_tenant_env', table_name='vector_db_connections')
    op.drop_index(op.f('ix_vector_db_connections_id'), table_name='vector_db_connections')
    op.drop_table('vector_db_connections')

    op.drop_index(op.f('ix_vector_db_types_slug'), table_name='vector_db_types')
    op.drop_index(op.f('ix_vector_db_types_id'), table_name='vector_db_types')
    op.drop_table('vector_db_types')

    # Restore items table (minimal schema — no data recovery)
    op.create_table(
        'items',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_items_id'), 'items', ['id'], unique=False)
    op.create_index(op.f('ix_items_title'), 'items', ['title'], unique=False)
