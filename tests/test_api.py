"""Tests for the FastAPI routes and API endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_ok(self, client):
        response = client.get("/health")
        assert response.json() == {"status": "ok"}


class TestIndexRoute:
    def test_get_index_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_index_contains_form(self, client):
        response = client.get("/")
        assert "<form" in response.text

    def test_index_has_labels_for_inputs(self, client):
        """Every input must have an associated label (accessibility check)."""
        from bs4 import BeautifulSoup

        soup = (
            BeautifulSoup(response.text, "html.parser")
            if (response := client.get("/"))
            else None
        )
        inputs = soup.find_all("input", {"type": "number"})
        for inp in inputs:
            inp_id = inp.get("id")
            if inp_id:
                label = soup.find("label", {"for": inp_id})
                assert label is not None, f"Input #{inp_id} has no associated label"

    def test_index_has_one_h1(self, client):
        from bs4 import BeautifulSoup

        response = client.get("/")
        soup = BeautifulSoup(response.text, "html.parser")
        h1s = soup.find_all("h1")
        assert len(h1s) == 1, f"Expected exactly one h1, found {len(h1s)}"

    def test_index_has_lang_attribute(self, client):
        response = client.get("/")
        assert 'lang="en"' in response.text


class TestApiAnalyzeSuccess:
    def test_normal_values_return_200(self, client, valid_payload):
        response = client.post("/api/analyze", json=valid_payload)
        assert response.status_code == 200

    def test_response_includes_disclaimer(self, client, valid_payload):
        response = client.post("/api/analyze", json=valid_payload)
        data = response.json()
        assert "disclaimer" in data
        assert "educational purposes" in data["disclaimer"]

    def test_response_has_results_list(self, client, valid_payload):
        response = client.post("/api/analyze", json=valid_payload)
        data = response.json()
        assert "results" in data
        assert isinstance(data["results"], list)
        assert len(data["results"]) == len(valid_payload["values"])

    def test_flagged_count_is_correct(self, client, flagged_payload):
        response = client.post("/api/analyze", json=flagged_payload)
        data = response.json()
        # hemoglobin 8.0 for male is LOW; fasting_glucose 120.0 is HIGH
        assert data["flagged_count"] == 2

    def test_normal_values_have_zero_flagged(self, client, valid_payload):
        response = client.post("/api/analyze", json=valid_payload)
        data = response.json()
        assert data["flagged_count"] == 0

    def test_statuses_are_correct(self, client, flagged_payload):
        response = client.post("/api/analyze", json=flagged_payload)
        data = response.json()
        statuses = {r["test_id"]: r["status"] for r in data["results"]}
        assert statuses["hemoglobin"] == "LOW"
        assert statuses["fasting_glucose"] == "HIGH"

    def test_has_critical_flag_for_critical_values(self, client, critical_payload):
        response = client.post("/api/analyze", json=critical_payload)
        data = response.json()
        assert data["has_critical"] is True

    def test_has_critical_false_for_normal_values(self, client, valid_payload):
        response = client.post("/api/analyze", json=valid_payload)
        data = response.json()
        assert data["has_critical"] is False

    def test_explanation_source_is_fallback_without_key(self, client, flagged_payload):
        """Without a Gemini key, explanation_source must be 'fallback'."""
        import os
        from unittest.mock import patch

        with patch.dict(os.environ, {}, clear=False):
            # Ensure no key is set by patching settings
            from unittest.mock import patch as upatch

            with upatch("app.explainer.get_settings") as mock_settings:
                setattr(mock_settings.return_value, "gemini_api_key", None)
                from app.explainer import _cached_llm_call

                _cached_llm_call.cache_clear()
                response = client.post("/api/analyze", json=flagged_payload)

        data = response.json()
        assert data["explanation_source"] == "fallback"


class TestApiAnalyzeValidation:
    def test_422_on_missing_sex(self, client):
        response = client.post("/api/analyze", json={"values": {"hemoglobin": 15.0}})
        assert response.status_code == 422

    def test_422_on_negative_value(self, client):
        response = client.post(
            "/api/analyze",
            json={"sex": "male", "values": {"hemoglobin": -1.0}},
        )
        assert response.status_code == 422

    def test_422_on_unknown_test_id(self, client):
        response = client.post(
            "/api/analyze",
            json={"sex": "male", "values": {"nonexistent_test": 5.0}},
        )
        assert response.status_code == 422

    def test_422_on_empty_values(self, client):
        response = client.post(
            "/api/analyze",
            json={"sex": "male", "values": {}},
        )
        assert response.status_code == 422

    def test_422_on_implausible_value(self, client):
        response = client.post(
            "/api/analyze",
            json={"sex": "male", "values": {"hemoglobin": 999.0}},
        )
        assert response.status_code == 422


class TestApiRateLimit:
    def test_429_after_exceeding_rate_limit(self, app):
        """Sending more than rate_limit_rpm requests should return 429."""
        from unittest.mock import patch

        # Set a very low rate limit for this test
        with patch("app.security.get_settings") as mock_settings:
            mock_settings.return_value.rate_limit_rpm = 2
            mock_settings.return_value.max_body_size = 10_240
            # Need to also patch in the route handler
            with patch("app.main.get_settings") as mock_main_settings:
                setattr(mock_main_settings.return_value, "gemini_api_key", None)
                mock_main_settings.return_value.rate_limit_rpm = 2
                mock_main_settings.return_value.cors_origins = []
                mock_main_settings.return_value.is_production = False
                mock_main_settings.return_value.docs_enabled = True

                test_client = TestClient(app, raise_server_exceptions=False)
                payload = {"sex": "male", "values": {"hemoglobin": 15.0}}

                # Clear rate limit state
                from app.security import _request_log

                _request_log.clear()

                responses = [
                    test_client.post("/api/analyze", json=payload) for _ in range(5)
                ]
                status_codes = [r.status_code for r in responses]
                assert 429 in status_codes


class TestSecurityHeaders:
    def test_security_headers_present_on_health(self, client):
        response = client.get("/health")
        assert "x-content-type-options" in response.headers
        assert response.headers["x-content-type-options"] == "nosniff"

    def test_x_frame_options_present(self, client):
        response = client.get("/")
        assert "x-frame-options" in response.headers
        assert response.headers["x-frame-options"] == "DENY"

    def test_content_security_policy_present(self, client):
        response = client.get("/")
        assert "content-security-policy" in response.headers

    def test_referrer_policy_present(self, client):
        response = client.get("/")
        assert "referrer-policy" in response.headers

    def test_no_store_on_analyze(self, client, valid_payload):
        response = client.post("/api/analyze", json=valid_payload)
        assert "cache-control" in response.headers
        assert "no-store" in response.headers["cache-control"]


class TestFormRoute:
    def test_form_submission_valid(self, client):
        response = client.post(
            "/analyze",
            data={"sex": "male", "hemoglobin": "15.0"},
        )
        # Should return results or redirect
        assert response.status_code in (200, 302, 303)

    def test_form_submission_no_sex_returns_422(self, client):
        response = client.post(
            "/analyze",
            data={"hemoglobin": "15.0"},
        )
        assert response.status_code == 422

    def test_critical_banner_in_results_html(self, client, critical_payload):
        """Results page must show a critical banner for critical values."""
        response = client.post(
            "/analyze",
            data={
                "sex": "male",
                "hemoglobin": "5.0",  # CRITICAL_LOW
                "fasting_glucose": "600.0",  # CRITICAL_HIGH
            },
        )
        assert response.status_code == 200
        assert "critical-banner" in response.text or "Urgent" in response.text

    def test_disclaimer_always_present_in_results(self, client):
        response = client.post(
            "/analyze",
            data={"sex": "male", "hemoglobin": "15.0"},
        )
        assert "educational purposes" in response.text.lower()
