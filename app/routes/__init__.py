"""Routes sub-package for LabLens.

Exposes a single ``router`` that registers all application routes.
"""

from __future__ import annotations

from app.routes.api import router as api_router
from app.routes.health import router as health_router
from app.routes.pages import router as pages_router

__all__ = ["api_router", "health_router", "pages_router"]
