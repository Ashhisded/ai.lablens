"""Health check route."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["ops"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint for Cloud Run and load balancers."""
    return {"status": "ok"}
