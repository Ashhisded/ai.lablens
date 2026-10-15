"""Tests for data integrity of reference_ranges.json."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

DATA_PATH = Path(__file__).parent.parent / "app" / "data" / "reference_ranges.json"


@pytest.fixture(scope="module")
def reference_data():
    """Load the reference data JSON."""
    with DATA_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def test_data_file_exists():
    assert DATA_PATH.exists(), "reference_ranges.json must exist"


def test_top_level_fields(reference_data):
    assert "version" in reference_data
    assert "source" in reference_data
    assert "last_reviewed" in reference_data
    assert "disclaimer" in reference_data
    assert "tests" in reference_data
    assert isinstance(reference_data["tests"], list)
    assert len(reference_data["tests"]) >= 14


def test_required_test_ids_present(reference_data):
    """All 14 required test IDs must be present."""
    required = {
        "hemoglobin",
        "wbc",
        "platelets",
        "fasting_glucose",
        "hba1c",
        "total_cholesterol",
        "ldl_cholesterol",
        "hdl_cholesterol",
        "triglycerides",
        "creatinine",
        "tsh",
        "alt",
        "vitamin_d",
        "ferritin",
    }
    present = {t["id"] for t in reference_data["tests"]}
    missing = required - present
    assert not missing, f"Missing required tests: {missing}"


def test_each_test_has_unit(reference_data):
    for test in reference_data["tests"]:
        assert "unit" in test and test["unit"], f"Test '{test.get('id', '?')}' missing unit"


def test_each_test_has_required_fields(reference_data):
    required_fields = {
        "id",
        "display_name",
        "unit",
        "plain_description",
        "ranges",
        "max_plausible",
    }
    for test in reference_data["tests"]:
        missing = required_fields - set(test.keys())
        assert not missing, f"Test '{test.get('id')}' missing fields: {missing}"


def test_each_test_has_plain_description(reference_data):
    for test in reference_data["tests"]:
        desc = test.get("plain_description", "")
        assert (
            desc and len(desc) > 10
        ), f"Test '{test.get('id')}' has missing or too short plain_description"


def test_range_ordering_is_valid(reference_data):
    """critical_low < low < high < critical_high where all are defined."""
    for test in reference_data["tests"]:
        for sex_key, bounds in test["ranges"].items():
            cl = bounds.get("critical_low")
            lo = bounds.get("low")
            hi = bounds.get("high")
            ch = bounds.get("critical_high")

            test_id = test["id"]

            if cl is not None and lo is not None:
                assert cl < lo, f"{test_id}/{sex_key}: critical_low ({cl}) must be < low ({lo})"
            if lo is not None and hi is not None:
                assert lo <= hi, f"{test_id}/{sex_key}: low ({lo}) must be <= high ({hi})"
            if hi is not None and ch is not None:
                assert hi < ch, f"{test_id}/{sex_key}: high ({hi}) must be < critical_high ({ch})"


def test_fallback_texts_present_where_expected(reference_data):
    """Tests with a low bound should have a fallback_low text, etc."""
    for test in reference_data["tests"]:
        has_low = any(b.get("low") is not None for b in test["ranges"].values())
        has_high = any(b.get("high") is not None for b in test["ranges"].values())
        if has_low:
            assert test.get(
                "fallback_low"
            ), f"Test '{test['id']}' has a low bound but no fallback_low"
        if has_high:
            assert test.get(
                "fallback_high"
            ), f"Test '{test['id']}' has a high bound but no fallback_high"


def test_max_plausible_is_positive(reference_data):
    for test in reference_data["tests"]:
        mp = test.get("max_plausible")
        assert (
            mp is not None and mp > 0
        ), f"Test '{test['id']}' max_plausible must be a positive number"


def test_ranges_structure(reference_data):
    """Each test must have ranges with 'all', 'male', or 'female' keys."""
    valid_keys = {"all", "male", "female"}
    for test in reference_data["tests"]:
        ranges = test.get("ranges", {})
        assert ranges, f"Test '{test['id']}' has empty ranges"
        for key in ranges:
            assert key in valid_keys, f"Test '{test['id']}' has unexpected range key: '{key}'"
