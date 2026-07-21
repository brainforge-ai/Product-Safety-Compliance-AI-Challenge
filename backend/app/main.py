"""FastAPI application entrypoint.

This module is intentionally thin: it wires together the app factory,
mounts routers, and defines the lifespan hook. No business logic should
live here, per the ports-and-adapters design in docs/ARCHITECTURE.md.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.routes_health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup/shutdown hooks (DB table creation, default forbidden list
    # loading, heavy model warm-up) are added in later phases.
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Product Safety Compliance AI System",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.include_router(health_router, prefix="/api/v1", tags=["health"])

    return app


app = create_app()
