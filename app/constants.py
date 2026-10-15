"""Shared string and numeric constants for LabLens.

Centralising magic values here removes duplication and makes future
updates a single-location change.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Medical disclaimer — shown on every results page and API response.
# This exact text must never be shortened; it is safety-critical.
# ---------------------------------------------------------------------------

MEDICAL_DISCLAIMER: str = (
    "This tool is for educational purposes only and is not medical advice. "
    "Reference ranges vary between laboratories. "
    "Always consult a qualified healthcare professional about your results."
)

# ---------------------------------------------------------------------------
# Explanation sources
# ---------------------------------------------------------------------------

SOURCE_LLM: str = "llm"
SOURCE_FALLBACK: str = "fallback"

# ---------------------------------------------------------------------------
# Critical status set used by the results renderer
# ---------------------------------------------------------------------------

# Imported lazily to avoid circular imports; see rules_engine.py for TestStatus.

# ---------------------------------------------------------------------------
# LLM behaviour
# ---------------------------------------------------------------------------

#: Gemini API call timeout in seconds.
#: Must stay ≤ 8 s so that the total round-trip fits inside Vercel's 10 s
#: serverless function limit even when the SDK adds retransmission overhead.
GEMINI_TIMEOUT: float = 8.0

#: Number of automatic retries on transient failures (0 = no retry).
GEMINI_RETRIES: int = 1

# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

#: Width of the sliding window for per-IP rate limiting.
RATE_LIMIT_WINDOW: float = 60.0  # seconds

# ---------------------------------------------------------------------------
# Request size
# ---------------------------------------------------------------------------

#: Maximum permitted request body in bytes (10 KB).
MAX_BODY_SIZE: int = 10_240

# ---------------------------------------------------------------------------
# LLM output safety — disallowed phrase patterns (regex source strings).
# Compiled in explainer.py; stored here so they can be unit-tested and
# updated without touching business logic.
# ---------------------------------------------------------------------------

DISALLOWED_PATTERN_SOURCES: list[str] = [
    r"\byou have\b",
    r"\bdiagnosed with\b",
    r"\byour condition\b",
    r"\bprescribe\b",
    r"\btake \d+\s?mg\b",
    r"\b\d+\s?mg\s+(once|twice|three times)\b",
    r"\bdo not see a doctor\b",
    r"\bno need to see\b",
    # Common medication names (small blocklist — extend as needed)
    (
        r"\b(metformin|insulin|aspirin|atorvastatin|lisinopril|levothyroxine"
        r"|warfarin|ibuprofen|acetaminophen|amoxicillin)\b"
    ),
]

# ---------------------------------------------------------------------------
# LLM system instruction
# ---------------------------------------------------------------------------

LLM_SYSTEM_INSTRUCTION: str = (
    "You are a health literacy assistant. "
    "Provide ONLY general educational information about lab tests. "
    "Write at approximately an 8th grade reading level. "
    "Use plain language a non-medical person can understand. "
    "You MUST follow these rules strictly:\n"
    "1. NEVER state a diagnosis or say the person has a disease.\n"
    "2. NEVER recommend or name any medication, drug, or dosage.\n"
    "3. NEVER suggest a treatment plan.\n"
    "4. NEVER advise the person to delay or avoid seeing a doctor.\n"
    "5. Use hedging language: 'can be associated with', "
    "'may indicate', 'is sometimes linked to'.\n"
    "6. End each explanation with a suggestion to discuss with a doctor.\n"
    "7. Keep each explanation under 80 words.\n"
    "8. Output valid JSON only, matching the requested schema."
)
