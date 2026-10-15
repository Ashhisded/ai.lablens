"""Gemini explanation provider with static fallback and LRU caching."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from functools import lru_cache
from typing import Protocol, cast, runtime_checkable

from app.config import get_settings
from app.constants import (
    DISALLOWED_PATTERN_SOURCES,
    GEMINI_RETRIES,
    GEMINI_TIMEOUT,
    LLM_SYSTEM_INSTRUCTION,
    SOURCE_FALLBACK,
    SOURCE_LLM,
)
from app.rules_engine import TestStatus, get_meta

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Safety constants
# ---------------------------------------------------------------------------

# Words/phrases that must not appear in LLM output — any match triggers fallback.
# Pattern sources are defined in constants.py so they can be independently tested.
_DISALLOWED_PATTERNS: list[re.Pattern[str]] = [
    re.compile(src, re.IGNORECASE) for src in DISALLOWED_PATTERN_SOURCES
]

_GEMINI_TIMEOUT = GEMINI_TIMEOUT
_GEMINI_RETRIES = GEMINI_RETRIES

# LLM system instruction — enforces educational tone and content limits.
_SYSTEM_INSTRUCTION = LLM_SYSTEM_INSTRUCTION


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


class FlaggedTest:
    """A single flagged test to explain."""

    __slots__ = ("test_id", "display_name", "unit", "status", "low", "high")

    def __init__(
        self,
        test_id: str,
        display_name: str,
        unit: str,
        status: TestStatus,
        low: float | None,
        high: float | None,
    ) -> None:
        """Initialise with test metadata."""
        self.test_id = test_id
        self.display_name = display_name
        self.unit = unit
        self.status = status
        self.low = low
        self.high = high


class ExplanationResult:
    """Result from an explanation provider."""

    __slots__ = ("explanations", "source")

    def __init__(self, explanations: dict[str, str], source: str) -> None:
        """Initialise with explanations and their source."""
        self.explanations = explanations
        self.source = source  # SOURCE_LLM or SOURCE_FALLBACK


# ---------------------------------------------------------------------------
# Provider protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class ExplanationProvider(Protocol):
    """Interface for explanation providers."""

    def explain(self, flagged: list[FlaggedTest]) -> ExplanationResult:
        """Produce plain-language explanations for flagged tests.

        Args:
            flagged: List of flagged test results needing explanation.

        Returns:
            An ExplanationResult with per-test text and source.
        """
        ...


# ---------------------------------------------------------------------------
# Static fallback provider
# ---------------------------------------------------------------------------


class StaticFallbackProvider:
    """Returns pre-written fallback explanations from the data file."""

    def explain(self, flagged: list[FlaggedTest]) -> ExplanationResult:
        """Return static fallback explanations.

        Args:
            flagged: List of flagged tests.

        Returns:
            ExplanationResult with source=SOURCE_FALLBACK.
        """
        explanations: dict[str, str] = {}
        for ft in flagged:
            meta = get_meta(ft.test_id)
            if ft.status in (TestStatus.LOW, TestStatus.CRITICAL_LOW):
                text = meta.get("fallback_low") or _generic_fallback(ft)
            else:
                text = meta.get("fallback_high") or _generic_fallback(ft)
            explanations[ft.test_id] = text
        return ExplanationResult(explanations=explanations, source=SOURCE_FALLBACK)


def _generic_fallback(ft: FlaggedTest) -> str:
    """Generate a generic safe fallback message for a test."""
    direction = "below" if ft.status in (TestStatus.LOW, TestStatus.CRITICAL_LOW) else "above"
    return (
        f"Your {ft.display_name} value is {direction} the typical reference range. "
        "Please discuss this result with your healthcare provider."
    )


# ---------------------------------------------------------------------------
# Cache key helper
# ---------------------------------------------------------------------------


def _cache_key(flagged: list[FlaggedTest]) -> str:
    """Compute a deterministic cache key for a set of flagged tests.

    Keyed by (test_id, status, sex-independent) — same inputs always hash the same.

    Args:
        flagged: List of flagged tests.

    Returns:
        A hex digest string.
    """
    items = sorted((ft.test_id, ft.status.value) for ft in flagged)
    payload = json.dumps(items, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


# ---------------------------------------------------------------------------
# LRU-cached inner call to avoid repeated identical API requests
# ---------------------------------------------------------------------------


@lru_cache(maxsize=128)
def _cached_llm_call(cache_key: str, flagged_json: str) -> dict[str, str] | None:
    """Execute the actual Gemini API call, cached by cache_key.

    SECURITY NOTE: flagged_json contains only validated test IDs, status enums,
    unit strings, and numeric range bounds — never raw user-supplied text.
    Prompt injection is structurally impossible because no user string reaches
    the LLM; only our controlled, schema-validated data does.

    Args:
        cache_key: Cache key (unused in body, drives LRU key).
        flagged_json: JSON string of structured test data to explain.

    Returns:
        Dict mapping test_id -> explanation, or None on failure.
    """
    settings = get_settings()
    if not settings.gemini_api_key:
        logger.info("GEMINI_API_KEY not set; using fallback explanations.")
        return None

    try:
        # Import here to avoid module-level import failure when key is absent.
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.gemini_api_key)

        prompt = (
            "Below is a JSON list of flagged lab test results. "
            "For each test, write a plain-language explanation "
            "following the system rules. "
            "Return a JSON object mapping each test_id to its explanation string.\n\n"
            f"{flagged_json}"
        )

        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_INSTRUCTION,
                temperature=0.3,
                response_mime_type="application/json",
                http_options=types.HttpOptions(timeout=int(_GEMINI_TIMEOUT * 1000)),
            ),
        )

        raw_text = response.text or ""
        parsed = json.loads(raw_text)
        if not isinstance(parsed, dict):
            logger.warning("LLM returned non-dict JSON; falling back.")
            return None
        return cast(dict[str, str], parsed)

    except json.JSONDecodeError:
        logger.warning("LLM returned malformed JSON; falling back.")
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM call failed (%s); falling back.", type(exc).__name__)
        return None


# ---------------------------------------------------------------------------
# Gemini provider
# ---------------------------------------------------------------------------


class GeminiProvider:
    """Calls the Gemini API for plain-language explanations.

    Falls back automatically to static explanations on any failure.
    """

    _fallback = StaticFallbackProvider()

    def explain(self, flagged: list[FlaggedTest]) -> ExplanationResult:
        """Produce explanations, using Gemini if available.

        Makes exactly one batched API call for all flagged tests.

        Args:
            flagged: List of flagged tests needing explanation.

        Returns:
            ExplanationResult with source=SOURCE_LLM or source=SOURCE_FALLBACK.
        """
        if not flagged:
            return ExplanationResult(explanations={}, source=SOURCE_FALLBACK)

        cache_key = _cache_key(flagged)
        flagged_data = [
            {
                "test_id": ft.test_id,
                "display_name": ft.display_name,
                "unit": ft.unit,
                "status": ft.status.value,
                "reference_low": ft.low,
                "reference_high": ft.high,
            }
            for ft in flagged
        ]
        flagged_json = json.dumps(flagged_data)

        raw = _cached_llm_call(cache_key, flagged_json)
        if raw is None:
            return self._fallback.explain(flagged)

        # Validate and sanitise each explanation.
        explanations: dict[str, str] = {}
        fallback_result = self._fallback.explain(flagged)

        for ft in flagged:
            text = raw.get(ft.test_id)
            if not isinstance(text, str) or not text.strip():
                logger.warning("LLM missing explanation for %s; using fallback.", ft.test_id)
                explanations[ft.test_id] = fallback_result.explanations[ft.test_id]
                continue
            if _contains_disallowed(text):
                logger.warning(
                    "LLM explanation for %s contains disallowed content; " "using fallback.",
                    ft.test_id,
                )
                explanations[ft.test_id] = fallback_result.explanations[ft.test_id]
                continue
            explanations[ft.test_id] = text.strip()

        # Determine source: SOURCE_LLM if at least one explanation came from the API.
        source = (
            SOURCE_LLM
            if any(
                explanations.get(ft.test_id) != fallback_result.explanations.get(ft.test_id)
                for ft in flagged
                if ft.test_id in fallback_result.explanations
            )
            else SOURCE_FALLBACK
        )
        return ExplanationResult(explanations=explanations, source=source)


def _contains_disallowed(text: str) -> bool:
    """Return True if text contains any disallowed pattern.

    Args:
        text: The explanation text to check.

    Returns:
        True if a disallowed pattern is found.
    """
    return any(pattern.search(text) for pattern in _DISALLOWED_PATTERNS)
