"""Tests for Pydantic request/response schemas."""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from app.schemas import AnalysisRequest, Sex


class TestAnalysisRequestValid:
    """Valid requests should parse without errors."""

    def test_minimal_valid(self):
        req = AnalysisRequest(sex=Sex.MALE, values={"hemoglobin": 15.0})
        assert req.sex == Sex.MALE
        assert req.values["hemoglobin"] == 15.0

    def test_female_sex(self):
        req = AnalysisRequest(sex=Sex.FEMALE, values={"wbc": 6.0})
        assert req.sex == Sex.FEMALE

    def test_with_age_band(self):
        from app.schemas import AgeBand

        req = AnalysisRequest(
            sex=Sex.MALE,
            age_band=AgeBand.ADULT_18_64,
            values={"hemoglobin": 15.0},
        )
        assert req.age_band == AgeBand.ADULT_18_64

    def test_multiple_values(self):
        req = AnalysisRequest(
            sex=Sex.MALE,
            values={"hemoglobin": 15.0, "wbc": 6.5, "platelets": 250.0},
        )
        assert len(req.values) == 3

    def test_zero_value_allowed(self):
        req = AnalysisRequest(sex=Sex.MALE, values={"tsh": 0.0})
        assert req.values["tsh"] == 0.0


class TestAnalysisRequestInvalid:
    """Invalid inputs must raise ValidationError."""

    def test_rejects_negative_value(self):
        with pytest.raises(ValidationError, match="non-negative"):
            AnalysisRequest(sex=Sex.MALE, values={"hemoglobin": -1.0})

    def test_rejects_nan(self):
        with pytest.raises(ValidationError, match="finite"):
            AnalysisRequest(sex=Sex.MALE, values={"hemoglobin": math.nan})

    def test_rejects_positive_infinity(self):
        with pytest.raises(ValidationError, match="finite"):
            AnalysisRequest(sex=Sex.MALE, values={"hemoglobin": math.inf})

    def test_rejects_negative_infinity(self):
        with pytest.raises(ValidationError, match="finite"):
            AnalysisRequest(sex=Sex.MALE, values={"hemoglobin": -math.inf})

    def test_rejects_unknown_test_id(self):
        with pytest.raises(ValidationError, match="Unknown test id"):
            AnalysisRequest(sex=Sex.MALE, values={"unknown_test": 5.0})

    def test_rejects_extra_fields(self):
        with pytest.raises(ValidationError):
            AnalysisRequest(
                sex=Sex.MALE,
                values={"hemoglobin": 15.0},
                extra_field="not_allowed",
            )

    def test_rejects_implausibly_large_value(self):
        # hemoglobin max_plausible is 25.0
        with pytest.raises(ValidationError, match="plausible maximum"):
            AnalysisRequest(sex=Sex.MALE, values={"hemoglobin": 100.0})

    def test_rejects_empty_values(self):
        with pytest.raises(ValidationError, match="At least one"):
            AnalysisRequest(sex=Sex.MALE, values={})

    def test_rejects_invalid_sex(self):
        with pytest.raises(ValidationError):
            AnalysisRequest(sex="other", values={"hemoglobin": 15.0})

    def test_rejects_string_value(self):
        with pytest.raises((ValidationError, ValueError)):
            AnalysisRequest(sex=Sex.MALE, values={"hemoglobin": "high"})

    def test_rejects_too_many_values(self):
        """Cannot submit more values than known tests."""
        from app.rules_engine import KNOWN_TEST_IDS

        # Create one more value than allowed by adding an unknown ID through
        # raw dict — this should fail on unknown test ID check first
        values = {tid: 1.0 for tid in list(KNOWN_TEST_IDS)[:5]}
        values["extra_unknown_test_that_does_not_exist"] = 1.0
        with pytest.raises(ValidationError):
            AnalysisRequest(sex=Sex.MALE, values=values)
