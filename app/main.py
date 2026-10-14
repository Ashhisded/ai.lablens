"""FastAPI application factory, routes, and middleware wiring."""

from __future__ import annotations

import contextlib
import logging
import uuid
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from app.config import get_settings
from app.explainer import FlaggedTest, GeminiProvider, StaticFallbackProvider
from app.rules_engine import (
    KNOWN_TEST_IDS,
    TestStatus,
    classify,
    get_bounds_for_display,
    get_meta,
)
from app.schemas import (
    MEDICAL_DISCLAIMER,
    AgeBand,
    AnalysisRequest,
    AnalysisResponse,
    Sex,
    TestResultItem,
)
from app.security import (
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware,
    add_no_store_header,
    check_rate_limit,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Critical status set (for banner logic)
# ---------------------------------------------------------------------------

_CRITICAL_STATUSES = {TestStatus.CRITICAL_LOW, TestStatus.CRITICAL_HIGH}

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        A configured FastAPI instance.
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

    # Middleware (applied in reverse order — last added runs first)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestSizeLimitMiddleware)
    app.add_middleware(GZipMiddleware, minimum_size=500)

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type"],
        )

    # Static files
    from pathlib import Path

    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # Templates
    templates_dir = Path(__file__).parent / "templates"
    templates = Jinja2Templates(directory=str(templates_dir))
    # Autoescape is on by default in Jinja2Templates for HTML extensions.

    # Providers
    provider = GeminiProvider()
    fallback_provider = StaticFallbackProvider()

    # -----------------------------------------------------------------------
    # Global exception handler — never leak stack traces
    # -----------------------------------------------------------------------

    @app.exception_handler(Exception)
    async def global_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Handle any unhandled exception gracefully."""
        request_id = str(uuid.uuid4())[:8]
        logger.exception(
            "Unhandled error [request_id=%s] type=%s",
            request_id,
            type(exc).__name__,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "An internal error occurred. Please try again later.",
                "request_id": request_id,
            },
        )

    # -----------------------------------------------------------------------
    # Routes
    # -----------------------------------------------------------------------

    @app.get("/health", tags=["ops"])
    async def health() -> dict[str, str]:
        """Health check endpoint for Cloud Run and load balancers."""
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse, tags=["ui"])
    async def index(request: Request) -> HTMLResponse:
        """Render the input form."""
        from app.rules_engine import _RAW_DATA  # noqa: PLC0415

        tests = _RAW_DATA["tests"]
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "tests": tests,
                "known_ids": list(KNOWN_TEST_IDS),
            },
        )

    @app.post("/analyze", response_class=HTMLResponse, tags=["ui"])
    async def analyze_form(
        request: Request,
    ) -> HTMLResponse:
        """Handle the HTML form submission (works without JS)."""
        form_data = await request.form()
        sex_raw = form_data.get("sex", "")
        age_band_raw = form_data.get("age_band", "") or None

        values: dict[str, float] = {}
        for key, val in form_data.multi_items():
            if key in KNOWN_TEST_IDS and val:
                with contextlib.suppress(ValueError):
                    values[key] = float(val)

        try:
            sex_enum = Sex(sex_raw)
        except ValueError:
            return templates.TemplateResponse(
                request,
                "index.html",
                {
                    "error": "Please select a biological sex.",
                    "tests": _get_tests_data(),
                    "known_ids": list(KNOWN_TEST_IDS),
                },
                status_code=422,
            )

        age_band_enum: AgeBand | None = None
        if age_band_raw:
            try:
                age_band_enum = AgeBand(age_band_raw)
            except ValueError:
                age_band_enum = None

        try:
            req = AnalysisRequest(sex=sex_enum, age_band=age_band_enum, values=values)
        except ValidationError as exc:
            errors = [e["msg"] for e in exc.errors()]
            return templates.TemplateResponse(
                request,
                "index.html",
                {
                    "error": "; ".join(errors),
                    "tests": _get_tests_data(),
                    "known_ids": list(KNOWN_TEST_IDS),
                },
                status_code=422,
            )

        result = _run_analysis(req, provider, fallback_provider)
        response = templates.TemplateResponse(
            request,
            "results.html",
            _template_context(result),
        )
        add_no_store_header(response)
        return response

    @app.post(
        "/api/analyze",
        tags=["api"],
        status_code=200,
    )
    async def analyze_api(
        request: Request,
        body: AnalysisRequest,
    ) -> JSONResponse:
        """Analyze lab values and return JSON results.

        Rate-limited to 20 requests per minute per IP.
        """
        rate_limit_response = check_rate_limit(request)
        if rate_limit_response is not None:
            return rate_limit_response

        result = _run_analysis(body, provider, fallback_provider)
        response_data = AnalysisResponse.model_validate(result).model_dump(mode="json")
        return JSONResponse(
            content=response_data,
            headers={"Cache-Control": "no-store"},
        )

    return app


# ---------------------------------------------------------------------------
# Shared analysis logic
# ---------------------------------------------------------------------------


def _get_tests_data() -> list[dict[str, Any]]:
    """Return the list of test definitions for template rendering."""
    from app.rules_engine import _RAW_DATA  # noqa: PLC0415

    return _RAW_DATA["tests"]


def _run_analysis(
    req: AnalysisRequest,
    provider: GeminiProvider,
    fallback_provider: StaticFallbackProvider,
) -> AnalysisResponse:
    """Run the rules engine and explainer for a given request.

    Args:
        req: The validated analysis request.
        provider: The primary explanation provider (Gemini).
        fallback_provider: The fallback explanation provider.

    Returns:
        A fully populated AnalysisResponse.
    """
    from app.rules_engine import Sex as EngineSex  # noqa: PLC0415

    engine_sex = EngineSex(req.sex.value)
    results: list[TestResultItem] = []
    flagged: list[FlaggedTest] = []

    for test_id, value in req.values.items():
        test_status = classify(test_id, value, engine_sex)
        meta = get_meta(test_id)
        low, high = get_bounds_for_display(test_id, engine_sex)
        item = TestResultItem(
            test_id=test_id,
            display_name=meta["display_name"],
            unit=meta["unit"],
            value=value,
            status=test_status,
            low=low,
            high=high,
        )
        results.append(item)
        if test_status != TestStatus.NORMAL:
            flagged.append(
                FlaggedTest(
                    test_id=test_id,
                    display_name=meta["display_name"],
                    unit=meta["unit"],
                    status=test_status,
                    low=low,
                    high=high,
                )
            )

    # Only call explainer if there are flagged tests.
    if flagged:
        explanation_result = provider.explain(flagged)
    else:
        explanation_result = fallback_provider.explain([])
        explanation_result.explanations = {}
        explanation_result.source = "fallback"

    # Attach explanations to result items.
    for item in results:
        item.explanation = explanation_result.explanations.get(item.test_id)

    has_critical = any(r.status in _CRITICAL_STATUSES for r in results)
    flagged_count = len(flagged)

    return AnalysisResponse(
        results=results,
        flagged_count=flagged_count,
        has_critical=has_critical,
        explanation_source=explanation_result.source,
        disclaimer=MEDICAL_DISCLAIMER,
    )


def _template_context(resp: AnalysisResponse) -> dict[str, Any]:
    """Build the Jinja2 template context from an AnalysisResponse."""
    return {
        "results": resp.results,
        "flagged_count": resp.flagged_count,
        "has_critical": resp.has_critical,
        "explanation_source": resp.explanation_source,
        "disclaimer": resp.disclaimer,
    }


# ---------------------------------------------------------------------------
# Application instance
# ---------------------------------------------------------------------------

app = create_app()

# Configure logging — minimal structured format, never logs health data.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
