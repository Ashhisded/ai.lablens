"""JSON API routes for programmatic access."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.explainer import GeminiProvider, StaticFallbackProvider
from app.routes.analysis import get_fallback_provider, get_gemini_provider, run_analysis
from app.schemas import AnalysisRequest, AnalysisResponse
from app.security import check_rate_limit

router = APIRouter(tags=["api"])


@router.post(
    "/api/analyze",
    status_code=200,
)
async def analyze_api(
    request: Request,
    body: AnalysisRequest,
    provider: GeminiProvider = Depends(get_gemini_provider),
    fallback_provider: StaticFallbackProvider = Depends(get_fallback_provider),
) -> JSONResponse:
    """Analyze lab values and return JSON results.

    Rate-limited to 20 requests per minute per IP.
    """
    rate_limit_response = check_rate_limit(request)
    if rate_limit_response is not None:
        return rate_limit_response

    result = run_analysis(body, provider=provider, fallback_provider=fallback_provider)
    response_data = AnalysisResponse.model_validate(result).model_dump(mode="json")
    return JSONResponse(
        content=response_data,
        headers={"Cache-Control": "no-store"},
    )
