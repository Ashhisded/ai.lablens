"""Custom exception classes and global error handlers for LabLens."""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from fastapi import Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.templating import templates

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain Exceptions
# ---------------------------------------------------------------------------


class LabLensError(Exception):
    """Base domain exception for LabLens application."""


class UnknownTestError(LabLensError):
    """Raised when an unrecognised test identifier is requested."""

    def __init__(self, test_id: str) -> None:
        """Initialise with the unknown test ID."""
        super().__init__(f"Unknown test ID: '{test_id}'")
        self.test_id = test_id


class PlausibilityError(LabLensError):
    """Raised when a lab value exceeds physiological plausibility limits."""


# ---------------------------------------------------------------------------
# Exception Handlers
# ---------------------------------------------------------------------------


def is_html_request(request: Request) -> bool:
    """Determine whether the client prefers an HTML response."""
    accept = request.headers.get("accept", "")
    return "text/html" in accept and not request.url.path.startswith("/api/")


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse | HTMLResponse:
    """Handle any uncaught exception gracefully without leaking tracebacks."""
    request_id = str(uuid.uuid4())[:8]
    logger.exception(
        "Unhandled error [request_id=%s] type=%s path=%s",
        request_id,
        type(exc).__name__,
        request.url.path,
    )

    if is_html_request(request):
        return templates.TemplateResponse(
            request,
            "500.html",
            {"request_id": request_id},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal error occurred. Please try again later.",
            "request_id": request_id,
        },
    )


async def not_found_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse | HTMLResponse:
    """Handle 404 Not Found errors with an accessible template or JSON."""
    status_code = getattr(exc, "status_code", status.HTTP_404_NOT_FOUND)
    if status_code == status.HTTP_404_NOT_FOUND:
        if is_html_request(request):
            return templates.TemplateResponse(
                request,
                "404.html",
                {"path": request.url.path},
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "Resource not found."},
        )

    # For other Starlette HTTPExceptions (e.g. 405 Method Not Allowed)
    detail = getattr(exc, "detail", "An error occurred.")
    return JSONResponse(
        status_code=status_code,
        content={"detail": detail},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all custom exception handlers on the FastAPI application."""
    app.add_exception_handler(StarletteHTTPException, not_found_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)
