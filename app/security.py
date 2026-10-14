"""Security helpers: rate limiting, headers, input sanitization."""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from ipaddress import ip_address

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Security header constants
# ---------------------------------------------------------------------------

_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "frame-ancestors 'none';"
)


def add_security_headers(response: Response) -> None:
    """Attach security headers to any response.

    Args:
        response: The FastAPI/Starlette response to modify.
    """
    response.headers["Content-Security-Policy"] = _CSP
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"


def add_no_store_header(response: Response) -> None:
    """Prevent caching of analysis responses containing health data.

    Args:
        response: The response to mark as non-cacheable.
    """
    response.headers["Cache-Control"] = "no-store"


# ---------------------------------------------------------------------------
# Security headers middleware
# ---------------------------------------------------------------------------


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to every response."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Process request and inject security headers.

        Args:
            request: The incoming request.
            call_next: The next middleware/handler in the chain.

        Returns:
            The response with security headers attached.
        """
        response = await call_next(request)
        add_security_headers(response)
        return response


# ---------------------------------------------------------------------------
# Request size limiting middleware
# ---------------------------------------------------------------------------


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests exceeding the configured body size limit."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Enforce maximum body size.

        Args:
            request: The incoming request.
            call_next: The next middleware/handler in the chain.

        Returns:
            413 if body is too large, otherwise the normal response.
        """
        settings = get_settings()
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > settings.max_body_size:
            return JSONResponse(
                status_code=413,
                content={"detail": "Request body too large."},
            )
        return await call_next(request)


# ---------------------------------------------------------------------------
# In-memory rate limiter
# ---------------------------------------------------------------------------

# ip -> list of request timestamps (epoch seconds)
_request_log: dict[str, list[float]] = defaultdict(list)
_WINDOW = 60.0  # seconds


def _get_client_ip(request: Request) -> str:
    """Extract the client IP, honouring X-Forwarded-For safely.

    Only the first (leftmost) address in X-Forwarded-For is used,
    and it is validated as a proper IP to prevent header injection.

    Args:
        request: The incoming request.

    Returns:
        A normalised IP string.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        candidate = forwarded.split(",")[0].strip()
        try:
            return str(ip_address(candidate))
        except ValueError:
            pass
    return request.client.host if request.client else "unknown"


def check_rate_limit(request: Request) -> JSONResponse | None:
    """Check whether the client has exceeded the rate limit.

    Args:
        request: The incoming request.

    Returns:
        A 429 JSONResponse if rate-limited, otherwise None.
    """
    settings = get_settings()
    ip = _get_client_ip(request)
    now = time.monotonic()
    window_start = now - _WINDOW

    # Prune timestamps outside the sliding window.
    timestamps = _request_log[ip]
    _request_log[ip] = [t for t in timestamps if t >= window_start]

    if len(_request_log[ip]) >= settings.rate_limit_rpm:
        retry_after = int(_WINDOW - (now - _request_log[ip][0]))
        logger.info(
            "Rate limit exceeded for IP (hash=%s)",
            hash(ip),  # Never log the raw IP
        )
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please wait before retrying."},
            headers={"Retry-After": str(max(retry_after, 1))},
        )

    _request_log[ip].append(now)
    return None
