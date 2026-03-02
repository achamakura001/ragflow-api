"""Alembic environment configuration.

Reads the database URL from envs/.env.{APP_ENV} via app.config.
Set APP_ENV before running migrations:
  APP_ENV=dev  alembic upgrade head
  APP_ENV=prod alembic upgrade head
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# ── Project imports ───────────────────────────────────────────────────────────
# Import settings to resolve the sync DB URL from the active env file
from app.config import get_settings

# Import ALL models so that Base.metadata contains every table.
# Add new model imports here as you create them.
from app.database import Base
from app.models import (  # noqa: F401
    EmbeddingProvider, TenantEmbeddingConfig,
    Tenant, TenantMember, TenantMemberRole, TenantPlan, User,
    VectorDbConnection, VectorDbEnv, VectorDbType,
)

# ── Alembic config ────────────────────────────────────────────────────────────
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override sqlalchemy.url from our settings (reads from envs/.env.{APP_ENV})
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.sync_database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (generates SQL script)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live DB connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,        # detect column type changes
            compare_server_default=True,  # detect default changes
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

