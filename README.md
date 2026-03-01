# ragflow-api

A Python 3.12 microservice built with **FastAPI** + **async SQLAlchemy** + **MySQL**.  
Designed to be easy to migrate to any cloud-managed MySQL-compatible database (AWS RDS, GCP Cloud SQL, Azure Database for MySQL, PlanetScale, etc.).

---

## Project Structure

```
ragflow-api/
├── app/
│   ├── main.py                   # FastAPI app factory & lifespan
│   ├── config.py                 # Pydantic-settings (env-driven)
│   ├── database.py               # Async SQLAlchemy engine & session
│   ├── models/                   # ORM models (SQLAlchemy)
│   │   └── item.py
│   ├── schemas/                  # Pydantic request/response schemas
│   │   └── item.py
│   ├── repositories/             # DB access layer (no business logic)
│   │   └── item_repository.py
│   ├── services/                 # Business logic layer
│   │   └── item_service.py
│   ├── routers/                  # FastAPI routers (HTTP layer)
│   │   ├── health.py
│   │   └── items.py
│   └── middleware/
│       └── logging.py            # Request/response logging
├── tests/
│   ├── conftest.py               # Shared fixtures (in-memory SQLite)
│   ├── unit/
│   │   └── test_item_service.py  # Pure unit tests (mocked repo)
│   └── integration/
│       └── test_items_router.py  # End-to-end HTTP tests (SQLite)
├── envs/
│   ├── .env.dev
│   ├── .env.qa
│   └── .env.prod
├── scripts/
│   ├── start_dev.sh
│   ├── start_qa.sh
│   ├── start_prod.sh
│   └── stop_server.sh
├── requirements.txt
├── requirements-dev.txt
└── pyproject.toml
```

---

## Quick Start

### 1. Create a virtual environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
# Runtime + dev/test tools
pip install -r requirements-dev.txt
```

### 3. Set up local MySQL

```sql
CREATE DATABASE ragflow_dev;
CREATE USER 'root'@'localhost' IDENTIFIED BY 'dev_password';
GRANT ALL PRIVILEGES ON ragflow_dev.* TO 'root'@'localhost';
```

Adjust `envs/.env.dev` values to match your local credentials.

### 4. Start the server

```bash
# Development (auto-reload)
bash scripts/start_dev.sh

# QA / staging
bash scripts/start_qa.sh

# Production (gunicorn + uvicorn workers, daemonised)
bash scripts/start_prod.sh

# Stop any running instance
bash scripts/stop_server.sh
```

The API will be available at <http://localhost:8000>.  
Interactive docs: <http://localhost:8000/docs>

---

## Running Tests

```bash
# All tests with coverage report
pytest

# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# Skip coverage
pytest --no-cov
```

Tests use **in-memory SQLite** via `aiosqlite` – no real MySQL instance needed.

---

## Migrating to a Cloud Database

1. Update the relevant `envs/.env.*` file:
   - Set `DB_HOST` to your cloud endpoint.
   - Set `DB_USER`, `DB_PASSWORD`, `DB_NAME`.
2. The SQLAlchemy URL is built automatically in `app/config.py`.
3. For SSL/TLS (required by most cloud providers), add `connect_args` in `app/database.py`:

```python
engine = create_async_engine(
    settings.database_url,
    connect_args={"ssl": {"ca": "/path/to/ca-cert.pem"}},
    ...
)
```

---

## Adding a New Domain

1. Create `app/models/my_model.py` (ORM model, extends `Base`).
2. Create `app/schemas/my_model.py` (Pydantic schemas).
3. Create `app/repositories/my_model_repository.py`.
4. Create `app/services/my_model_service.py`.
5. Create `app/routers/my_models.py` and register it in `app/main.py`.
6. Add unit tests in `tests/unit/` and integration tests in `tests/integration/`.

---

## Environment Variables Reference

| Variable                   | Default          | Description                        |
|----------------------------|------------------|------------------------------------|
| `APP_ENV`                  | `dev`            | `dev` / `qa` / `prod`              |
| `DEBUG`                    | `true`           | Enable SQLAlchemy echo & debug     |
| `DB_HOST`                  | `localhost`      | MySQL host or cloud endpoint       |
| `DB_PORT`                  | `3306`           | MySQL port                         |
| `DB_USER`                  | `root`           | DB username                        |
| `DB_PASSWORD`              | *(empty)*        | DB password                        |
| `DB_NAME`                  | `ragflow_dev`    | Database / schema name             |
| `DB_POOL_SIZE`             | `5`              | SQLAlchemy connection pool size    |
| `DB_POOL_RECYCLE`          | `3600`           | Recycle connections (cloud-safe)   |
| `SECRET_KEY`               | *(placeholder)*  | JWT signing key                    |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60`          | Token TTL                          |
| `ALLOWED_ORIGINS`          | `["*"]`          | CORS origin list                   |
