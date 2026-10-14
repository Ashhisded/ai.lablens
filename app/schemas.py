"""Pydantic request and response models for LabLens."""

from __future__ import annotations

import math
from enum import Enum
from typing import Any

from pydantic import BaseModel, field_validator

from app.rules_engine import KNOWN_TEST_IDS, MAX_PLAUSIBLE, TestStatus

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

MEDICAL_DISCLAIMER = (
    "This tool is for educational purposes only and is not medical advice. "
    "Reference ranges vary between laboratories. "
    "Always consult a qualified healthcare professional about your results."
)


class Sex(str, Enum):
    """Biological sex for range selection."""

    MALE = "male"
    FEMALE = "female"


class AgeBand(str, Enum):
    """Optional age band for context (ranges remain adult-only)."""

    UNDER_18 = "under_18"
    ADULT_18_64 = "18_64"
    SENIOR_65_PLUS = "65_plus"


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class AnalysisRequest(BaseModel):
    """Incoming analysis request from the user."""

    model_config = {"extra": "forbid"}

    sex: Sex
    age_band: AgeBand | None = None
    values: dict[str, float]

    @field_validator("values")
    @classmethod
    def validate_values(cls, v: dict[str, Any]) -> dict[str, float]:
        """Validate each test value for plausibility and known IDs."""
        if not v:
            raise ValueError("At least one test value is required.")
        if len(v) > len(KNOWN_TEST_IDS):
            raise ValueError(f"Too many values. Maximum is {len(KNOWN_TEST_IDS)}.")
        cleaned: dict[str, float] = {}
        for test_id, raw_value in v.items():
            if test_id not in KNOWN_TEST_IDS:
                raise ValueError(f"Unknown test id: '{test_id}'.")
            value = float(raw_value)
            if not math.isfinite(value):
                raise ValueError(f"Value for '{test_id}' must be a finite number.")
            if value < 0:
                raise ValueError(f"Value for '{test_id}' must be non-negative.")
            max_val = MAX_PLAUSIBLE.get(test_id)
            if max_val is not None and value > max_val:
                raise ValueError(
                    f"Value for '{test_id}' ({value}) exceeds the "
                    f"physiologically plausible maximum ({max_val})."
                )
            cleaned[test_id] = value
        return cleaned


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class TestResultItem(BaseModel):
    """Result for a single lab test."""

    test_id: str
    display_name: str
    unit: str
    value: float
    status: TestStatus
    low: float | None
    high: float | None
    explanation: str | None = None


class AnalysisResponse(BaseModel):
    """Full analysis response returned to the client."""

    results: list[TestResultItem]
    flagged_count: int
    has_critical: bool
    explanation_source: str  # "llm" or "fallback"
    disclaimer: str = MEDICAL_DISCLAIMER
