"""Pure rules engine: classify lab values against reference ranges.

No I/O, no network calls, no globals mutated after startup.
"""

from __future__ import annotations

import json
import logging
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DATA_PATH = Path(__file__).parent / "data" / "reference_ranges.json"


class TestStatus(str, Enum):
    """Classification of a single lab value."""

    CRITICAL_LOW = "CRITICAL_LOW"
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL_HIGH = "CRITICAL_HIGH"


class Sex(str, Enum):
    """Biological sex used for sex-specific reference ranges."""

    MALE = "male"
    FEMALE = "female"


class LabLensError(Exception):
    """Base domain error for LabLens."""


class UnknownTestError(LabLensError):
    """Raised when an unrecognised test ID is requested."""

    def __init__(self, test_id: str) -> None:
        """Initialise with the unknown test ID."""
        super().__init__(f"Unknown test ID: '{test_id}'")
        self.test_id = test_id


# ---------------------------------------------------------------------------
# Data loading — runs once at module import
# ---------------------------------------------------------------------------


def _load_reference_data() -> dict[str, Any]:
    """Load and return the raw reference data JSON."""
    with _DATA_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def _build_index(
    data: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, float], dict[str, Any]]:
    """Build a fast lookup index from the reference data.

    Returns:
        A tuple of (ranges_index, max_plausible_index, meta_index).
    """
    ranges_index: dict[str, Any] = {}
    max_plausible_index: dict[str, float] = {}
    meta_index: dict[str, Any] = {}

    for test in data["tests"]:
        tid = test["id"]
        ranges_index[tid] = test["ranges"]
        max_plausible_index[tid] = test["max_plausible"]
        meta_index[tid] = {
            "display_name": test["display_name"],
            "unit": test["unit"],
            "plain_description": test["plain_description"],
            "fallback_low": test.get("fallback_low"),
            "fallback_high": test.get("fallback_high"),
        }

    return ranges_index, max_plausible_index, meta_index


_RAW_DATA = _load_reference_data()
_RANGES_INDEX, MAX_PLAUSIBLE, _META_INDEX = _build_index(_RAW_DATA)

# Public set of valid test IDs.
KNOWN_TEST_IDS: frozenset[str] = frozenset(_RANGES_INDEX.keys())


# ---------------------------------------------------------------------------
# Pure classification functions
# ---------------------------------------------------------------------------


def _get_bounds(test_id: str, sex: Sex) -> dict[str, float | None]:
    """Retrieve the numeric bounds for a test and sex.

    Prefers sex-specific bounds; falls back to 'all'.

    Args:
        test_id: The test identifier.
        sex: The patient's biological sex.

    Returns:
        A dict with keys low, high, critical_low, critical_high (any may be None).

    Raises:
        UnknownTestError: If test_id is not in the known set.
    """
    if test_id not in _RANGES_INDEX:
        raise UnknownTestError(test_id)
    ranges = _RANGES_INDEX[test_id]
    return ranges.get(sex.value) or ranges.get("all") or {}


def classify(test_id: str, value: float, sex: Sex) -> TestStatus:
    """Classify a single lab value as NORMAL, HIGH, LOW, or CRITICAL.

    Boundary rule: a value exactly equal to low or high is NORMAL.

    Args:
        test_id: The test identifier string.
        value: The numeric lab result.
        sex: The patient's biological sex for sex-specific ranges.

    Returns:
        A TestStatus enum member.

    Raises:
        UnknownTestError: If test_id is not recognised.
    """
    bounds = _get_bounds(test_id, sex)

    critical_low = bounds.get("critical_low")
    low = bounds.get("low")
    high = bounds.get("high")
    critical_high = bounds.get("critical_high")

    if critical_low is not None and value < critical_low:
        return TestStatus.CRITICAL_LOW
    if low is not None and value < low:
        return TestStatus.LOW
    if critical_high is not None and value > critical_high:
        return TestStatus.CRITICAL_HIGH
    if high is not None and value > high:
        return TestStatus.HIGH
    return TestStatus.NORMAL


def get_bounds_for_display(test_id: str, sex: Sex) -> tuple[float | None, float | None]:
    """Return (low, high) bounds for display purposes.

    Args:
        test_id: The test identifier.
        sex: The patient's biological sex.

    Returns:
        A tuple of (low, high) where either may be None.
    """
    bounds = _get_bounds(test_id, sex)
    return bounds.get("low"), bounds.get("high")


def get_meta(test_id: str) -> dict[str, Any]:
    """Return display metadata for a test.

    Args:
        test_id: The test identifier.

    Returns:
        Dict with display_name, unit, plain_description, fallback_low, fallback_high.

    Raises:
        UnknownTestError: If test_id is not recognised.
    """
    if test_id not in _META_INDEX:
        raise UnknownTestError(test_id)
    return _META_INDEX[test_id]
