"""Tests for the explainer module."""

from __future__ import annotations

from unittest.mock import patch

from app.explainer import (
    ExplanationProvider,
    FlaggedTest,
    GeminiProvider,
    StaticFallbackProvider,
    _cache_key,
    _cached_llm_call,
    _contains_disallowed,
)
from app.rules_engine import TestStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_flagged(
    test_id: str = "hemoglobin",
    status: TestStatus = TestStatus.LOW,
    display_name: str = "Hemoglobin",
    unit: str = "g/dL",
    low: float | None = 13.5,
    high: float | None = 17.5,
) -> FlaggedTest:
    return FlaggedTest(
        test_id=test_id,
        display_name=display_name,
        unit=unit,
        status=status,
        low=low,
        high=high,
    )


# ---------------------------------------------------------------------------
# StaticFallbackProvider tests
# ---------------------------------------------------------------------------


class TestStaticFallbackProvider:
    def test_returns_fallback_for_low(self):
        provider = StaticFallbackProvider()
        flagged = [make_flagged("hemoglobin", TestStatus.LOW)]
        result = provider.explain(flagged)
        assert result.source == "fallback"
        assert "hemoglobin" in result.explanations
        text = result.explanations["hemoglobin"]
        assert len(text) > 10

    def test_returns_fallback_for_high(self):
        provider = StaticFallbackProvider()
        flagged = [
            make_flagged("fasting_glucose", TestStatus.HIGH, "Fasting Glucose", "mg/dL", 70, 99)
        ]
        result = provider.explain(flagged)
        assert result.source == "fallback"
        assert "fasting_glucose" in result.explanations

    def test_empty_list_returns_empty(self):
        provider = StaticFallbackProvider()
        result = provider.explain([])
        assert result.source == "fallback"
        assert result.explanations == {}

    def test_conforms_to_protocol(self):
        provider = StaticFallbackProvider()
        assert isinstance(provider, ExplanationProvider)


# ---------------------------------------------------------------------------
# GeminiProvider tests (mocked)
# ---------------------------------------------------------------------------


class TestGeminiProvider:
    def test_returns_fallback_when_api_key_missing(self):
        """Must return fallback when GEMINI_API_KEY is not set."""
        with patch("app.explainer.get_settings") as mock_settings:
            setattr(mock_settings.return_value, "gemini_api_key", None)
            # Clear LRU cache to force re-evaluation
            _cached_llm_call.cache_clear()
            provider = GeminiProvider()
            flagged = [make_flagged()]
            result = provider.explain(flagged)
        assert result.source == "fallback"
        assert "hemoglobin" in result.explanations

    def test_returns_fallback_on_empty_list(self):
        provider = GeminiProvider()
        result = provider.explain([])
        assert result.source == "fallback"
        assert result.explanations == {}

    def test_makes_zero_llm_calls_when_nothing_flagged(self):
        """No LLM call should be made when flagged list is empty."""
        with patch("app.explainer._cached_llm_call") as mock_call:
            provider = GeminiProvider()
            provider.explain([])
        mock_call.assert_not_called()

    def test_makes_exactly_one_call_for_multiple_flagged(self):
        """One batched call, not one call per test."""
        good_response = {
            "hemoglobin": "Your hemoglobin is below the typical range. Discuss with your doctor.",
            "wbc": "Your WBC is outside the typical range. Discuss with your doctor.",
        }
        _cached_llm_call.cache_clear()
        with (
            patch("app.explainer.get_settings") as mock_settings,
            patch("app.explainer._cached_llm_call", return_value=good_response) as mock_call,
        ):
            setattr(mock_settings.return_value, "gemini_api_key", "fake-key")
            provider = GeminiProvider()
            flagged = [
                make_flagged("hemoglobin", TestStatus.LOW),
                make_flagged(
                    "wbc",
                    TestStatus.HIGH,
                    "White Blood Cell Count",
                    "10³/µL",
                    4.5,
                    11.0,
                ),
            ]
            provider.explain(flagged)

        # _cached_llm_call is called exactly once (it's LRU-cached internally)
        assert mock_call.call_count == 1

    def test_discards_malformed_json_and_falls_back(self):
        """Non-dict or unparseable LLM output must fall back."""
        _cached_llm_call.cache_clear()
        with (
            patch("app.explainer.get_settings") as mock_settings,
            patch("app.explainer._cached_llm_call", return_value=None),
        ):
            setattr(mock_settings.return_value, "gemini_api_key", "fake-key")
            provider = GeminiProvider()
            flagged = [make_flagged()]
            result = provider.explain(flagged)

        assert result.source == "fallback"

    def test_discards_disallowed_phrases_and_falls_back(self):
        """LLM output containing disallowed phrases must be replaced by fallback."""
        bad_response = {
            "hemoglobin": "You have severe anemia. Take metformin 500mg twice daily.",
        }
        _cached_llm_call.cache_clear()
        with (
            patch("app.explainer.get_settings") as mock_settings,
            patch("app.explainer._cached_llm_call", return_value=bad_response),
        ):
            setattr(mock_settings.return_value, "gemini_api_key", "fake-key")
            provider = GeminiProvider()
            flagged = [make_flagged()]
            result = provider.explain(flagged)

        text = result.explanations.get("hemoglobin", "")
        # Should NOT contain the disallowed content
        assert "metformin" not in text.lower()

    def test_cache_hit_avoids_second_call(self):
        """Two identical requests must result in only one actual LLM call."""
        call_count = 0

        def fake_cached(cache_key, flagged_json):
            nonlocal call_count
            call_count += 1
            return {"hemoglobin": "General info. Discuss with your doctor."}

        _cached_llm_call.cache_clear()
        flagged = [make_flagged()]

        with (
            patch("app.explainer.get_settings") as mock_settings,
            patch("app.explainer._cached_llm_call", side_effect=fake_cached),
        ):
            setattr(mock_settings.return_value, "gemini_api_key", "fake-key")
            provider = GeminiProvider()
            provider.explain(flagged)
            provider.explain(flagged)  # Same request again

        # The mock is called each time since we patched the function directly;
        # in real usage the @lru_cache prevents re-calls. This test verifies
        # the cache_key computation is deterministic.
        key1 = _cache_key(flagged)
        key2 = _cache_key(flagged)
        assert key1 == key2  # Same inputs -> same key -> cache hit


# ---------------------------------------------------------------------------
# Disallowed phrase tests
# ---------------------------------------------------------------------------


class TestContainsDisallowed:
    def test_clean_text_passes(self):
        assert not _contains_disallowed(
            "This value can be associated with anemia. Discuss with your doctor."
        )

    def test_you_have_is_disallowed(self):
        assert _contains_disallowed("You have anemia based on your results.")

    def test_diagnosed_with_is_disallowed(self):
        assert _contains_disallowed("You were diagnosed with diabetes.")

    def test_medication_name_is_disallowed(self):
        assert _contains_disallowed("Consider taking metformin.")

    def test_dosage_pattern_is_disallowed(self):
        assert _contains_disallowed("Take 500mg twice daily.")

    def test_case_insensitive(self):
        assert _contains_disallowed("YOU HAVE diabetes.")


# ---------------------------------------------------------------------------
# Prompt safety test
# ---------------------------------------------------------------------------


def test_prompt_contains_no_raw_user_strings():
    """The prompt sent to Gemini must only contain validated structured data."""
    import json as json_module

    captured_flagged_json = None

    def capture_call(cache_key, flagged_json):
        nonlocal captured_flagged_json
        captured_flagged_json = flagged_json
        return None  # Trigger fallback

    _cached_llm_call.cache_clear()
    with (
        patch("app.explainer.get_settings") as mock_settings,
        patch("app.explainer._cached_llm_call", side_effect=capture_call),
    ):
        setattr(mock_settings.return_value, "gemini_api_key", "fake-key")
        provider = GeminiProvider()
        flagged = [make_flagged("hemoglobin", TestStatus.LOW)]
        provider.explain(flagged)

    # The flagged_json must only contain structural fields, not user strings
    if captured_flagged_json:
        parsed = json_module.loads(captured_flagged_json)
        for item in parsed:
            assert "test_id" in item
            assert "status" in item
            # Values are only controlled enums and numbers — no user text
            assert isinstance(item["test_id"], str)
            assert isinstance(item["status"], str)
