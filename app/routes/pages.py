"""HTML page routes (Home, Analyzer form, Results, and About pages)."""

from __future__ import annotations

import contextlib
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from pydantic import ValidationError

from app.explainer import GeminiProvider, StaticFallbackProvider
from app.routes.analysis import (
    build_template_context,
    get_fallback_provider,
    get_gemini_provider,
    get_tests_data,
    run_analysis,
)
from app.rules_engine import KNOWN_TEST_IDS
from app.schemas import AgeBand, AnalysisRequest, Sex
from app.security import add_no_store_header
from app.templating import templates

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ui"])


@router.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    """Render the landing home page."""
    return templates.TemplateResponse(
        request,
        "home.html",
        {"current_page": "home"},
    )


@router.get("/analyze", response_class=HTMLResponse)
async def analyze_page(request: Request) -> HTMLResponse:
    """Render the blood test analyzer input form."""
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "current_page": "analyze",
            "tests": get_tests_data(),
            "known_ids": list(KNOWN_TEST_IDS),
        },
    )


@router.get("/about", response_class=HTMLResponse)
async def about(request: Request) -> HTMLResponse:
    """Render the about and clinical methodology page."""
    return templates.TemplateResponse(
        request,
        "about.html",
        {"current_page": "about"},
    )


@router.post("/analyze", response_class=HTMLResponse)
async def analyze_form(
    request: Request,
    provider: GeminiProvider = Depends(get_gemini_provider),
    fallback_provider: StaticFallbackProvider = Depends(get_fallback_provider),
) -> HTMLResponse:
    """Handle the HTML form submission (works without JS)."""
    form_data = await request.form()
    sex_raw = str(form_data.get("sex") or "")
    age_band_raw = str(form_data.get("age_band") or "") or None

    values: dict[str, float] = {}
    for key, val in form_data.multi_items():
        if isinstance(val, str) and key in KNOWN_TEST_IDS and val.strip():
            with contextlib.suppress(ValueError):
                values[key] = float(val)

    try:
        sex_enum = Sex(sex_raw)
    except ValueError:
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "current_page": "analyze",
                "error": "Please select a biological sex.",
                "tests": get_tests_data(),
                "known_ids": list(KNOWN_TEST_IDS),
            },
            status_code=422,
        )

    age_band_enum: AgeBand | None = None
    if age_band_raw:
        with contextlib.suppress(ValueError):
            age_band_enum = AgeBand(age_band_raw)

    try:
        req = AnalysisRequest(sex=sex_enum, age_band=age_band_enum, values=values)
    except ValidationError as exc:
        errors = [e["msg"] for e in exc.errors()]
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "current_page": "analyze",
                "error": "; ".join(errors),
                "tests": get_tests_data(),
                "known_ids": list(KNOWN_TEST_IDS),
            },
            status_code=422,
        )

    result = run_analysis(req, provider=provider, fallback_provider=fallback_provider)
    context = {
        "current_page": "results",
        **build_template_context(result),
    }
    response = templates.TemplateResponse(
        request,
        "results.html",
        context,
    )
    add_no_store_header(response)
    return response
