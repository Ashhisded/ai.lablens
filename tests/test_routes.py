"""Tests for app/routes/ sub-modules (pages, api, health, analysis) and accessibility."""

from __future__ import annotations

from pathlib import Path

import pytest
from bs4 import BeautifulSoup


class TestPagesRouter:
    """Test all HTML page endpoints for 200 status, landmarks, and content."""

    def test_get_home_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "Understand your blood test results" in response.text
        assert 'href="/analyze"' in response.text

    def test_get_home_landmarks(self, client):
        response = client.get("/")
        soup = BeautifulSoup(response.text, "html.parser")
        assert soup.find("header") is not None
        assert soup.find("nav") is not None
        assert soup.find("main") is not None
        assert soup.find("footer") is not None

    def test_get_home_aria_current(self, client):
        response = client.get("/")
        soup = BeautifulSoup(response.text, "html.parser")
        home_link = soup.find("nav").find("a", href="/")
        assert home_link.get("aria-current") == "page"

    def test_get_analyze_returns_200(self, client):
        response = client.get("/analyze")
        assert response.status_code == 200
        assert "<form" in response.text

    def test_get_analyze_has_sample_and_clear_buttons(self, client):
        response = client.get("/analyze")
        soup = BeautifulSoup(response.text, "html.parser")
        assert soup.find(id="fill-sample-btn") is not None
        assert soup.find(id="clear-form-btn") is not None

    def test_get_analyze_aria_current(self, client):
        response = client.get("/analyze")
        soup = BeautifulSoup(response.text, "html.parser")
        analyze_link = soup.find("nav").find("a", href="/analyze")
        assert analyze_link.get("aria-current") == "page"

    def test_get_about_returns_200(self, client):
        response = client.get("/about")
        assert response.status_code == 200
        assert "Clinical Methodology" in response.text or "Rules Engine" in response.text

    def test_get_about_aria_current(self, client):
        response = client.get("/about")
        soup = BeautifulSoup(response.text, "html.parser")
        about_link = soup.find("nav").find("a", href="/about")
        assert about_link.get("aria-current") == "page"

    def test_custom_404_html_page(self, client):
        response = client.get("/non-existent-page-url", headers={"accept": "text/html"})
        assert response.status_code == 404
        assert "Page Not Found" in response.text
        assert "404" in response.text

    def test_custom_404_api_json(self, client):
        response = client.get("/api/non-existent-route", headers={"accept": "application/json"})
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data


class TestPagesRouterAnalyzeFormSuccess:
    """Test POST /analyze HTML form submissions."""

    def test_valid_form_post_returns_200(self, client):
        response = client.post(
            "/analyze",
            data={"sex": "male", "hemoglobin": "15.0"},
        )
        assert response.status_code == 200

    def test_valid_form_post_shows_results(self, client):
        response = client.post(
            "/analyze",
            data={"sex": "female", "hemoglobin": "12.0"},
        )
        assert "Results" in response.text

    def test_result_has_disclaimer(self, client):
        response = client.post(
            "/analyze",
            data={"sex": "male", "fasting_glucose": "90.0"},
        )
        assert "educational purposes" in response.text.lower()

    def test_no_cache_header_on_results(self, client):
        response = client.post(
            "/analyze",
            data={"sex": "male", "hemoglobin": "15.0"},
        )
        assert response.headers.get("cache-control") == "no-store"

    def test_flagged_value_shows_status_chip(self, client):
        # Hemoglobin 8.0 g/dL for male is LOW
        response = client.post(
            "/analyze",
            data={"sex": "male", "hemoglobin": "8.0"},
        )
        assert response.status_code == 200
        assert "Low" in response.text

    def test_critical_value_shows_banner(self, client):
        # Hemoglobin 4.0 g/dL for male is CRITICAL_LOW
        response = client.post(
            "/analyze",
            data={"sex": "male", "hemoglobin": "4.0"},
        )
        assert response.status_code == 200
        assert "Critical" in response.text or "Urgent" in response.text

    def test_results_table_has_caption_and_scope(self, client):
        response = client.post(
            "/analyze",
            data={"sex": "male", "hemoglobin": "15.0"},
        )
        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table")
        assert table is not None
        assert table.find("caption") is not None
        for th in table.find_all("th"):
            assert th.get("scope") in ("col", "row")

    def test_results_has_print_button(self, client):
        response = client.post(
            "/analyze",
            data={"sex": "male", "hemoglobin": "15.0"},
        )
        soup = BeautifulSoup(response.text, "html.parser")
        assert soup.find(id="print-btn") is not None


class TestPagesRouterAnalyzeFormValidationErrors:
    def test_missing_sex_returns_422(self, client):
        response = client.post(
            "/analyze",
            data={"hemoglobin": "15.0"},
        )
        assert response.status_code == 422

    def test_missing_sex_shows_error_message(self, client):
        response = client.post(
            "/analyze",
            data={"hemoglobin": "15.0"},
        )
        assert (
            "sex" in response.text.lower()
            or "problem" in response.text.lower()
            or "error" in response.text.lower()
        )

    def test_invalid_sex_returns_422(self, client):
        response = client.post(
            "/analyze",
            data={"sex": "other_value", "hemoglobin": "15.0"},
        )
        assert response.status_code == 422

    def test_no_values_returns_422(self, client):
        response = client.post(
            "/analyze",
            data={"sex": "male"},
        )
        assert response.status_code == 422


class TestAccessibilityAndSafetyRequirements:
    """Automated accessibility, safety, and contrast compliance tests."""

    def test_no_safe_filter_in_any_template(self):
        """Strict verification: Jinja2 '|safe' must NEVER be used."""
        template_dir = Path(__file__).parent.parent / "app" / "templates"
        for html_file in template_dir.glob("*.html"):
            content = html_file.read_text(encoding="utf-8")
            assert "|safe" not in content, f"Forbidden |safe filter found in {html_file.name}"
            assert "| safe" not in content, f"Forbidden | safe filter found in {html_file.name}"

    def test_skip_link_on_all_pages(self, client):
        for path in ["/", "/analyze", "/about"]:
            response = client.get(path)
            soup = BeautifulSoup(response.text, "html.parser")
            skip_link = soup.find("a", class_="skip-link")
            assert skip_link is not None, f"Skip link missing on {path}"
            assert skip_link.get("href") == "#main-content"

    def test_single_h1_on_all_pages(self, client):
        for path in ["/", "/analyze", "/about"]:
            response = client.get(path)
            soup = BeautifulSoup(response.text, "html.parser")
            h1s = soup.find_all("h1")
            assert len(h1s) == 1, f"Expected exactly 1 h1 on {path}, found {len(h1s)}"

    def test_lang_attribute_on_all_pages(self, client):
        for path in ["/", "/analyze", "/about"]:
            response = client.get(path)
            assert 'lang="en"' in response.text

    def test_wcag_contrast_ratios(self):
        """Verify that color tokens meet the WCAG AA 4.5:1 minimum contrast requirement."""

        def hex_to_rgb(hex_str: str) -> tuple[float, float, float]:
            h = hex_str.lstrip("#")
            return tuple(int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]

        def relative_luminance(rgb: tuple[float, float, float]) -> float:
            lum = []
            for c in rgb:
                if c <= 0.04045:
                    lum.append(c / 12.92)
                else:
                    lum.append(((c + 0.055) / 1.055) ** 2.4)
            return 0.2126 * lum[0] + 0.7152 * lum[1] + 0.0722 * lum[2]

        def contrast_ratio(hex1: str, hex2: str) -> float:
            l1 = relative_luminance(hex_to_rgb(hex1))
            l2 = relative_luminance(hex_to_rgb(hex2))
            lighter = max(l1, l2)
            darker = min(l1, l2)
            return (lighter + 0.05) / (darker + 0.05)

        # Light theme tests (against surface #ffffff or bg #f8fafc)
        white = "#ffffff"
        assert contrast_ratio("#0f172a", white) >= 4.5  # --color-text
        assert contrast_ratio("#475569", white) >= 4.5  # --color-text-muted
        assert contrast_ratio("#0369a1", white) >= 4.5  # --color-primary
        assert contrast_ratio("#15803d", white) >= 4.5  # --color-normal
        assert contrast_ratio("#b45309", white) >= 4.5  # --color-low
        assert contrast_ratio("#c2410c", white) >= 4.5  # --color-high
        assert contrast_ratio("#b91c1c", white) >= 4.5  # --color-critical

        # Dark theme tests (against dark surface #1e293b)
        dark_surface = "#1e293b"
        assert contrast_ratio("#f8fafc", dark_surface) >= 4.5  # dark --color-text
        assert contrast_ratio("#cbd5e1", dark_surface) >= 4.5  # dark --color-text-muted
        assert contrast_ratio("#38bdf8", dark_surface) >= 4.5  # dark --color-primary
        assert contrast_ratio("#4ade80", dark_surface) >= 4.5  # dark --color-normal
        assert contrast_ratio("#fbbf24", dark_surface) >= 4.5  # dark --color-low
        assert contrast_ratio("#fb923c", dark_surface) >= 4.5  # dark --color-high
        assert contrast_ratio("#f87171", dark_surface) >= 4.5  # dark --color-critical


class TestAnalysisModule:
    def test_run_analysis_returns_response(self):
        from app.routes.analysis import run_analysis
        from app.schemas import AnalysisRequest, Sex

        req = AnalysisRequest(sex=Sex.MALE, values={"hemoglobin": 15.0})
        result = run_analysis(req)
        assert result.disclaimer != ""
        assert len(result.results) == 1
        assert len(result.results[0].questions_to_ask) > 0

    def test_build_template_context_has_counts(self):
        from app.routes.analysis import build_template_context, run_analysis
        from app.schemas import AnalysisRequest, Sex

        req = AnalysisRequest(sex=Sex.FEMALE, values={"hemoglobin": 12.0})
        result = run_analysis(req)
        ctx = build_template_context(result)
        assert "normal_count" in ctx
        assert "low_count" in ctx
        assert "high_count" in ctx
        assert "critical_count" in ctx


class TestDirectHandlerExecution:
    """Directly test async route handlers and error handlers for complete coverage."""

    @pytest.mark.asyncio
    async def test_analyze_form_direct_valid(self):
        from starlette.datastructures import FormData
        from starlette.requests import Request

        from app.explainer import GeminiProvider, StaticFallbackProvider
        from app.routes.pages import analyze_form

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/analyze",
            "headers": [(b"accept", b"text/html")],
        }
        req = Request(scope)
        req._form = FormData([("sex", "male"), ("age_band", "adult"), ("hemoglobin", "15.0")])

        res = await analyze_form(
            req, provider=GeminiProvider(), fallback_provider=StaticFallbackProvider()
        )
        assert res.status_code == 200
        assert "no-store" in res.headers.get("cache-control", "")

    @pytest.mark.asyncio
    async def test_analyze_form_direct_invalid_age_band(self):
        from starlette.datastructures import FormData
        from starlette.requests import Request

        from app.explainer import GeminiProvider, StaticFallbackProvider
        from app.routes.pages import analyze_form

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/analyze",
            "headers": [],
        }
        req = Request(scope)
        req._form = FormData(
            [("sex", "female"), ("age_band", "non_existent_band"), ("hemoglobin", "13.0")]
        )

        res = await analyze_form(
            req, provider=GeminiProvider(), fallback_provider=StaticFallbackProvider()
        )
        assert res.status_code == 200

    @pytest.mark.asyncio
    async def test_analyze_form_direct_missing_sex(self):
        from starlette.datastructures import FormData
        from starlette.requests import Request

        from app.explainer import GeminiProvider, StaticFallbackProvider
        from app.routes.pages import analyze_form

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/analyze",
            "headers": [],
        }
        req = Request(scope)
        req._form = FormData([("hemoglobin", "15.0")])

        res = await analyze_form(
            req, provider=GeminiProvider(), fallback_provider=StaticFallbackProvider()
        )
        assert res.status_code == 422
        assert "select a biological sex" in res.body.decode()

    @pytest.mark.asyncio
    async def test_analyze_form_direct_validation_error(self):
        from starlette.datastructures import FormData
        from starlette.requests import Request

        from app.explainer import GeminiProvider, StaticFallbackProvider
        from app.routes.pages import analyze_form

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/analyze",
            "headers": [],
        }
        req = Request(scope)
        # Empty values trigger AnalysisRequest validation error
        req._form = FormData([("sex", "male")])

        res = await analyze_form(
            req, provider=GeminiProvider(), fallback_provider=StaticFallbackProvider()
        )
        assert res.status_code == 422


class TestDirectErrorHandlers:
    """Test custom exception handlers for HTML and JSON branches."""

    @pytest.mark.asyncio
    async def test_global_exception_handler_html(self):
        from starlette.requests import Request

        from app.errors import global_exception_handler

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/some-page",
            "headers": [(b"accept", b"text/html,application/xhtml+xml")],
        }
        req = Request(scope)
        res = await global_exception_handler(req, RuntimeError("Database down"))
        assert res.status_code == 500
        assert "500" in res.body.decode() or "Something went wrong" in res.body.decode()

    @pytest.mark.asyncio
    async def test_global_exception_handler_json(self):
        from starlette.requests import Request

        from app.errors import global_exception_handler

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/analyze",
            "headers": [(b"accept", b"application/json")],
        }
        req = Request(scope)
        res = await global_exception_handler(req, ValueError("Invalid state"))
        assert res.status_code == 500
        assert b"request_id" in res.body

    @pytest.mark.asyncio
    async def test_not_found_handler_method_not_allowed(self):
        from starlette.exceptions import HTTPException as StarletteHTTPException
        from starlette.requests import Request

        from app.errors import not_found_exception_handler

        scope = {
            "type": "http",
            "method": "PUT",
            "path": "/api/analyze",
            "headers": [],
        }
        req = Request(scope)
        exc = StarletteHTTPException(status_code=405, detail="Method Not Allowed")
        res = await not_found_exception_handler(req, exc)
        assert res.status_code == 405
        assert b"Method Not Allowed" in res.body
