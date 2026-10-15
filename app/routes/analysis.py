"""Shared analysis business logic used by both the HTML and JSON routes."""

from __future__ import annotations

from typing import Any, cast

from app.constants import SOURCE_FALLBACK
from app.explainer import ExplanationResult, FlaggedTest, GeminiProvider, StaticFallbackProvider
from app.rules_engine import TestStatus, classify, get_bounds_for_display, get_meta
from app.schemas import MEDICAL_DISCLAIMER, AnalysisRequest, AnalysisResponse, TestResultItem

# Statuses that trigger the critical banner.
CRITICAL_STATUSES: frozenset[TestStatus] = frozenset(
    {TestStatus.CRITICAL_LOW, TestStatus.CRITICAL_HIGH}
)

# Module-level providers — instantiated once, shared across requests.
_gemini_provider = GeminiProvider()
_fallback_provider = StaticFallbackProvider()


def get_gemini_provider() -> GeminiProvider:
    """FastAPI dependency yielding the primary Gemini explanation provider."""
    return _gemini_provider


def get_fallback_provider() -> StaticFallbackProvider:
    """FastAPI dependency yielding the fallback explanation provider."""
    return _fallback_provider


def get_tests_data() -> list[dict[str, Any]]:
    """Return the list of test definitions for template rendering."""
    from app.rules_engine import _RAW_DATA  # noqa: PLC0415

    return cast(list[dict[str, Any]], _RAW_DATA["tests"])


def run_analysis(
    req: AnalysisRequest,
    provider: GeminiProvider | None = None,
    fallback_provider: StaticFallbackProvider | None = None,
) -> AnalysisResponse:
    """Run the rules engine and explainer for a given request.

    Args:
        req: The validated analysis request.
        provider: Primary explanation provider (defaults to GeminiProvider).
        fallback_provider: Fallback provider (defaults to StaticFallbackProvider).

    Returns:
        A fully populated AnalysisResponse.
    """
    from app.rules_engine import Sex as EngineSex  # noqa: PLC0415

    provider = provider or _gemini_provider
    fallback_provider = fallback_provider or _fallback_provider

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
            questions_to_ask=meta.get("questions_to_ask", []),
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

    explanation_result = _explain(flagged, provider, fallback_provider)

    # Attach explanations to result items.
    for item in results:
        item.explanation = explanation_result.explanations.get(item.test_id)

    has_critical = any(r.status in CRITICAL_STATUSES for r in results)

    return AnalysisResponse(
        results=results,
        flagged_count=len(flagged),
        has_critical=has_critical,
        explanation_source=explanation_result.source,
        disclaimer=MEDICAL_DISCLAIMER,
    )


def _explain(
    flagged: list[FlaggedTest],
    provider: GeminiProvider,
    fallback_provider: StaticFallbackProvider,
) -> ExplanationResult:
    """Call the appropriate explanation provider.

    Args:
        flagged: Tests that need explanation.
        provider: Primary explanation provider.
        fallback_provider: Fallback provider.

    Returns:
        An ExplanationResult from the Gemini or fallback provider.
    """
    if flagged:
        return provider.explain(flagged)
    # No flagged tests — return empty fallback result.
    result = fallback_provider.explain([])
    result.explanations = {}
    result.source = SOURCE_FALLBACK
    return result


def build_template_context(resp: AnalysisResponse) -> dict[str, Any]:
    """Build the Jinja2 template context from an AnalysisResponse.

    Args:
        resp: The completed analysis response.

    Returns:
        A dict ready to pass to ``TemplateResponse``.
    """
    normal_count = sum(1 for r in resp.results if r.status == TestStatus.NORMAL)
    low_count = sum(1 for r in resp.results if r.status == TestStatus.LOW)
    high_count = sum(1 for r in resp.results if r.status == TestStatus.HIGH)
    critical_count = sum(1 for r in resp.results if r.status in CRITICAL_STATUSES)

    return {
        "results": resp.results,
        "flagged_count": resp.flagged_count,
        "normal_count": normal_count,
        "low_count": low_count,
        "high_count": high_count,
        "critical_count": critical_count,
        "has_critical": resp.has_critical,
        "explanation_source": resp.explanation_source,
        "disclaimer": resp.disclaimer,
    }
