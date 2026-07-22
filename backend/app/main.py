"""FastAPI application entrypoint.

This module is intentionally thin: it wires together the app factory,
mounts routers, and defines the lifespan hook. No business logic should
live here, per the ports-and-adapters design in docs/ARCHITECTURE.md.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes_health import router as health_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.infra.db.session import create_db_and_tables, create_db_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings

    # Toggling ENABLE_PERSISTENCE changes only this wiring; no service/route
    # code branches on the flag (ARCHITECTURE.md Section 8).
    if settings.enable_persistence:
        app.state.db_engine = create_db_engine(settings.database_url)
        create_db_and_tables(app.state.db_engine)

    # Default forbidden list loading and heavy model warm-up are added in
    # later phases.
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(
        title="Product Safety Compliance AI System",
        version="0.1.0",
        lifespan=lifespan,
        # Swagger UI at /docs, ReDoc at /redoc, raw schema at /openapi.json.
        # Set explicitly (matching FastAPI's defaults) so the interactive
        # API docs are a documented, intentional part of the app rather
        # than an implicit default.
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.include_router(health_router, prefix="/api", tags=["health"])

    return app


app = create_app()
