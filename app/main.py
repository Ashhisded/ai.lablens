"""FastAPI application factory and middleware wiring for LabLens."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.errors import register_exception_handlers
from app.routes import api_router, health_router, pages_router
from app.security import RequestSizeLimitMiddleware, SecurityHeadersMiddleware

logger = logging.getLogger(__name__)

# Configure logging — minimal structured format, never logs health data.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        A configured FastAPI instance with all middleware and routes registered.
    """
    settings = get_settings()

    docs_url = None if settings.is_production else "/docs"
    redoc_url = None if settings.is_production else "/redoc"

    app = FastAPI(
        title="LabLens",
        description=(
            "AI-assisted lab report explainer. "
            "Understand your blood test results in plain language."
        ),
        version="1.0.0",
        docs_url=docs_url,
        redoc_url=redoc_url,
    )

    _register_middleware(app, settings)
    _mount_static(app)
    _register_routes(app)
    register_exception_handlers(app)

    return app


def _register_middleware(app: FastAPI, settings: object) -> None:
    """Attach all middleware to the application.

    Middleware is applied in reverse order — last added runs first.

    Args:
        app: The FastAPI application instance.
        settings: Application settings (used for CORS configuration).
    """
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestSizeLimitMiddleware)
    app.add_middleware(GZipMiddleware, minimum_size=500)

    cors_origins = getattr(settings, "cors_origins", [])
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type"],
        )


def _mount_static(app: FastAPI) -> None:
    """Mount the static files directory.

    Args:
        app: The FastAPI application instance.
    """
    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


def _register_routes(app: FastAPI) -> None:
    """Include all sub-routers.

    Args:
        app: The FastAPI application instance.
    """
    app.include_router(health_router)
    app.include_router(pages_router)
    app.include_router(api_router)


# ---------------------------------------------------------------------------
# Application instance — used by uvicorn and the ASGI server.
# ---------------------------------------------------------------------------

app = create_app()
