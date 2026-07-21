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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup/shutdown hooks (DB table creation, default forbidden list
    # loading, heavy model warm-up) are added in later phases.
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
