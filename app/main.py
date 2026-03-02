"""
Application entry point.
"""

import logging

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import dispose_db, init_db
from app.middleware.logging import RequestLoggingMiddleware
from app.routers import auth, health, tenant, vectordb, embedding

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup / shutdown lifecycle."""
    logger.info("Starting %s [%s]", settings.APP_NAME, settings.APP_ENV)
    await init_db()
    yield
    logger.info("Shutting down %s", settings.APP_NAME)
    await dispose_db()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    # ── Middleware ────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(health.router, tags=["Health"])
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
    app.include_router(tenant.router, prefix="/api/v1/tenants", tags=["Tenants"])
    app.include_router(vectordb.router, prefix="/api/v1/vector-dbs", tags=["Vector DBs"])
    app.include_router(embedding.router, prefix="/api/v1/embeddings", tags=["Embeddings"])

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        workers=settings.WORKERS,
        reload=settings.RELOAD,
        log_level=settings.LOG_LEVEL.lower(),
    )
