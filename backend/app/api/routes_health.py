"""Liveness/readiness endpoint."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe for load balancers and orchestrators."""
    return {"status": "ok"}
