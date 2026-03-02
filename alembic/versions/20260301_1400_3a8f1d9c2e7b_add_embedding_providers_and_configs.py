"""add_embedding_providers_and_configs

Revision ID: 3a8f1d9c2e7b
Revises: f7090923539f
Create Date: 2026-03-01 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '3a8f1d9c2e7b'
down_revision: Union[str, Sequence[str], None] = 'f7090923539f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── Seed data ─────────────────────────────────────────────────────────────────

_OPENAI_PROPS = [
    {
        "name": "api_key",
        "label": "API Key",
        "type": "password",
        "required": True,
        "secret": True,
        "placeholder": "sk-…",
        "description": "OpenAI API key from https://platform.openai.com/api-keys",
        "default": None,
    },
    {
        "name": "base_url",
        "label": "Base URL",
        "type": "string",
        "required": False,
        "secret": False,
        "placeholder": "https://api.openai.com/v1",
        "description": "Override the API base URL (e.g. for Azure OpenAI or a proxy)",
        "default": "https://api.openai.com/v1",
    },
]

_OLLAMA_PROPS = [
    {
        "name": "base_url",
        "label": "Server URL",
        "type": "string",
        "required": True,
        "secret": False,
        "placeholder": "http://localhost:11434",
        "description": "URL of the locally running Ollama server",
        "default": "http://localhost:11434",
    },
    {
        "name": "filter_embedding",
        "label": "Filter Embedding Models",
        "type": "boolean",
        "required": False,
        "secret": False,
        "placeholder": "",
        "description": "When enabled, only returns models with embedding-related names",
        "default": True,
    },
]

_GEMINI_PROPS = [
    {
        "name": "api_key",
        "label": "API Key",
        "type": "password",
        "required": True,
        "secret": True,
        "placeholder": "AIzaSy…",
        "description": "Google AI API key from https://aistudio.google.com/app/apikey",
        "default": None,
    },
    {
        "name": "base_url",
        "label": "Base URL",
        "type": "string",
        "required": False,
        "secret": False,
        "placeholder": "https://generativelanguage.googleapis.com/v1beta",
        "description": "Override the Gemini REST API base URL",
        "default": "https://generativelanguage.googleapis.com/v1beta",
    },
]


def upgrade() -> None:
    """Create embedding_providers and tenant_embedding_configs tables."""

    # ---------- embedding_providers (catalogue) ----------
    op.create_table(
        'embedding_providers',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('slug', sa.String(length=64), nullable=False),
        sa.Column('display_name', sa.String(length=128), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('models_url', sa.String(length=512), nullable=False),
        sa.Column('property_schema', sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug'),
    )
    op.create_index(op.f('ix_embedding_providers_id'), 'embedding_providers', ['id'], unique=False)
    op.create_index(op.f('ix_embedding_providers_slug'), 'embedding_providers', ['slug'], unique=True)

    # ---------- seed providers ----------
    providers_table = sa.table(
        'embedding_providers',
        sa.column('slug', sa.String),
        sa.column('display_name', sa.String),
        sa.column('description', sa.String),
        sa.column('models_url', sa.String),
        sa.column('property_schema', sa.JSON),
    )
    op.bulk_insert(
        providers_table,
        [
            {
                'slug': 'openai',
                'display_name': 'OpenAI',
                'description': 'OpenAI text embedding models (text-embedding-3-small, text-embedding-3-large, etc.)',
                'models_url': 'https://api.openai.com/v1/models',
                'property_schema': _OPENAI_PROPS,
            },
            {
                'slug': 'ollama',
                'display_name': 'Ollama',
                'description': 'Local embedding models served by Ollama (nomic-embed-text, all-minilm, mxbai-embed-large, etc.)',
                'models_url': '{base_url}/api/tags',
                'property_schema': _OLLAMA_PROPS,
            },
            {
                'slug': 'gemini',
                'display_name': 'Google Gemini',
                'description': 'Google Gemini embedding models (text-embedding-004, embedding-001, etc.)',
                'models_url': 'https://generativelanguage.googleapis.com/v1beta/models',
                'property_schema': _GEMINI_PROPS,
            },
        ],
    )

    # ---------- tenant_embedding_configs (tenant-scoped) ----------
    op.create_table(
        'tenant_embedding_configs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('provider_id', sa.Integer(), nullable=False),
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
        ),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['provider_id'], ['embedding_providers.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_tenant_embedding_configs_id'),
        'tenant_embedding_configs', ['id'], unique=False,
    )
    op.create_index(
        'ix_emb_cfg_tenant_env',
        'tenant_embedding_configs', ['tenant_id', 'environment'], unique=False,
    )


def downgrade() -> None:
    """Drop embedding tables (catalogue data is lost)."""
    op.drop_index('ix_emb_cfg_tenant_env', table_name='tenant_embedding_configs')
    op.drop_index(op.f('ix_tenant_embedding_configs_id'), table_name='tenant_embedding_configs')
    op.drop_table('tenant_embedding_configs')

    op.drop_index(op.f('ix_embedding_providers_slug'), table_name='embedding_providers')
    op.drop_index(op.f('ix_embedding_providers_id'), table_name='embedding_providers')
    op.drop_table('embedding_providers')
