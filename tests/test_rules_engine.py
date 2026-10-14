"""Tests for the pure rules engine."""

from __future__ import annotations

import pytest

from app.rules_engine import (
    KNOWN_TEST_IDS,
    Sex,
    TestStatus,
    UnknownTestError,
    classify,
    get_bounds_for_display,
    get_meta,
)

# ---------------------------------------------------------------------------
# Basic classification tests
# ---------------------------------------------------------------------------


class TestClassifyHemoglobin:
    """Hemoglobin has sex-specific ranges."""

    def test_normal_male(self):
        assert classify("hemoglobin", 15.0, Sex.MALE) == TestStatus.NORMAL

    def test_normal_female(self):
        assert classify("hemoglobin", 13.0, Sex.FEMALE) == TestStatus.NORMAL

    def test_low_male(self):
        # Male low threshold is 13.5; value 13.0 is LOW
        assert classify("hemoglobin", 13.0, Sex.MALE) == TestStatus.LOW

    def test_low_female(self):
        # Female low threshold is 12.0; value 11.0 is LOW
        assert classify("hemoglobin", 11.0, Sex.FEMALE) == TestStatus.LOW

    def test_high_male(self):
        # Male high threshold is 17.5; 18.0 is HIGH
        assert classify("hemoglobin", 18.0, Sex.MALE) == TestStatus.HIGH

    def test_high_female(self):
        # Female high is 15.5; 16.0 is HIGH
        assert classify("hemoglobin", 16.0, Sex.FEMALE) == TestStatus.HIGH

    def test_critical_low(self):
        # Critical low is 7.0 for both sexes
        assert classify("hemoglobin", 5.0, Sex.MALE) == TestStatus.CRITICAL_LOW
        assert classify("hemoglobin", 5.0, Sex.FEMALE) == TestStatus.CRITICAL_LOW

    def test_critical_high(self):
        assert classify("hemoglobin", 21.0, Sex.MALE) == TestStatus.CRITICAL_HIGH

    def test_sex_specific_same_value_different_status(self):
        """13.0 g/dL is LOW for male but NORMAL for female."""
        assert classify("hemoglobin", 13.0, Sex.MALE) == TestStatus.LOW
        assert classify("hemoglobin", 13.0, Sex.FEMALE) == TestStatus.NORMAL

    def test_boundary_at_low_is_normal(self):
        """Value exactly at the low boundary must be NORMAL."""
        assert classify("hemoglobin", 13.5, Sex.MALE) == TestStatus.NORMAL
        assert classify("hemoglobin", 12.0, Sex.FEMALE) == TestStatus.NORMAL

    def test_boundary_at_high_is_normal(self):
        """Value exactly at the high boundary must be NORMAL."""
        assert classify("hemoglobin", 17.5, Sex.MALE) == TestStatus.NORMAL
        assert classify("hemoglobin", 15.5, Sex.FEMALE) == TestStatus.NORMAL


class TestClassifyGlucose:
    """Fasting glucose has two-sided range."""

    def test_normal(self):
        assert classify("fasting_glucose", 85.0, Sex.MALE) == TestStatus.NORMAL

    def test_low(self):
        assert classify("fasting_glucose", 65.0, Sex.MALE) == TestStatus.LOW

    def test_high(self):
        assert classify("fasting_glucose", 110.0, Sex.MALE) == TestStatus.HIGH

    def test_critical_low(self):
        assert classify("fasting_glucose", 30.0, Sex.MALE) == TestStatus.CRITICAL_LOW

    def test_critical_high(self):
        assert classify("fasting_glucose", 600.0, Sex.MALE) == TestStatus.CRITICAL_HIGH

    def test_boundary_low(self):
        assert classify("fasting_glucose", 70.0, Sex.MALE) == TestStatus.NORMAL

    def test_boundary_high(self):
        assert classify("fasting_glucose", 99.0, Sex.MALE) == TestStatus.NORMAL


class TestClassifyOnesSidedRanges:
    """Tests for one-sided ranges (only high OR only low bound)."""

    def test_cholesterol_high_only_normal(self):
        # Total cholesterol has only an upper bound
        assert classify("total_cholesterol", 180.0, Sex.MALE) == TestStatus.NORMAL

    def test_cholesterol_high_only_high(self):
        assert classify("total_cholesterol", 220.0, Sex.MALE) == TestStatus.HIGH

    def test_cholesterol_boundary(self):
        # At boundary (199) is NORMAL
        assert classify("total_cholesterol", 199.0, Sex.MALE) == TestStatus.NORMAL

    def test_hdl_low_only_normal_male(self):
        # HDL has only a lower bound
        assert classify("hdl_cholesterol", 55.0, Sex.MALE) == TestStatus.NORMAL

    def test_hdl_low_only_low_male(self):
        assert classify("hdl_cholesterol", 35.0, Sex.MALE) == TestStatus.LOW

    def test_hdl_low_only_boundary_male(self):
        assert classify("hdl_cholesterol", 40.0, Sex.MALE) == TestStatus.NORMAL

    def test_hdl_low_only_low_female(self):
        # Female HDL low is 50.0
        assert classify("hdl_cholesterol", 45.0, Sex.FEMALE) == TestStatus.LOW

    def test_hdl_boundary_female(self):
        assert classify("hdl_cholesterol", 50.0, Sex.FEMALE) == TestStatus.NORMAL

    def test_hba1c_high_only_normal(self):
        assert classify("hba1c", 5.0, Sex.MALE) == TestStatus.NORMAL

    def test_hba1c_high_only_high(self):
        assert classify("hba1c", 6.0, Sex.MALE) == TestStatus.HIGH


class TestUnknownTestId:
    """Unknown test IDs must raise UnknownTestError."""

    def test_raises_on_unknown_id(self):
        with pytest.raises(UnknownTestError):
            classify("nonexistent_test", 5.0, Sex.MALE)

    def test_error_message_contains_id(self):
        with pytest.raises(UnknownTestError, match="nonexistent_test"):
            classify("nonexistent_test", 5.0, Sex.MALE)

    def test_get_meta_raises_on_unknown(self):
        with pytest.raises(UnknownTestError):
            get_meta("bad_id")

    def test_get_bounds_raises_on_unknown(self):
        with pytest.raises(UnknownTestError):
            get_bounds_for_display("bad_id", Sex.MALE)


# ---------------------------------------------------------------------------
# Parametrized table-driven tests across all known tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("test_id", list(KNOWN_TEST_IDS))
def test_get_meta_returns_required_fields(test_id):
    """Every test must have required metadata fields."""
    meta = get_meta(test_id)
    assert "display_name" in meta
    assert "unit" in meta
    assert "plain_description" in meta
    assert meta["display_name"]
    assert meta["unit"]


@pytest.mark.parametrize("test_id", list(KNOWN_TEST_IDS))
def test_get_bounds_does_not_raise(test_id):
    """get_bounds_for_display must not raise for any known test and sex."""
    get_bounds_for_display(test_id, Sex.MALE)
    get_bounds_for_display(test_id, Sex.FEMALE)


@pytest.mark.parametrize("test_id", list(KNOWN_TEST_IDS))
def test_classify_normal_for_midpoint(test_id):
    """A mid-range value should classify as NORMAL for each test."""
    low, high = get_bounds_for_display(test_id, Sex.MALE)
    if low is not None and high is not None:
        mid = (low + high) / 2
        result = classify(test_id, mid, Sex.MALE)
        assert (
            result == TestStatus.NORMAL
        ), f"{test_id}: midpoint {mid} classified as {result}"
