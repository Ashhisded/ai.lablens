# LabLens — AI-Assisted Lab Report Explainer

> **Understand your blood test results in plain language.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## What is LabLens?

LabLens is a web application that helps ordinary people — patients, caregivers, and the health-curious — understand their blood test results without a medical degree. Users enter numeric values from their lab report, and LabLens:

1. **Classifies** each value against standard adult reference ranges (deterministic, no AI)
2. **Explains** any abnormal values in plain language using Google Gemini AI
3. **Falls back** gracefully to static explanations if AI is unavailable

LabLens addresses the healthcare accessibility gap: millions of people receive lab results they cannot interpret, leading to unnecessary anxiety or, worse, ignoring important findings. LabLens bridges that gap as an educational tool — always pointing users to their doctor for real guidance.

---

## Problem & Impact

- **Health literacy** is a major barrier to effective self-care, especially in underserved communities.
- Lab reports are often written in clinical jargon with no plain-language support.
- LabLens empowers patients to have *informed conversations* with their doctors.
- Relevant to all three challenge themes: **healthcare accessibility**, **patient monitoring**, and **health literacy**.

---

## Features

- ✅ 14 standard blood tests (CBC, metabolic, cholesterol, thyroid, vitamins)
- ✅ Sex-specific reference ranges (haemoglobin, creatinine, HDL, ferritin)
- ✅ Five-level classification: CRITICAL_LOW / LOW / NORMAL / HIGH / CRITICAL_HIGH
- ✅ Plain-language AI explanations via Google Gemini (batched, cached, safe)
- ✅ Graceful fallback to static explanations — **app never crashes due to LLM**
- ✅ Critical value urgent banner (static, non-AI)
- ✅ Prominent medical disclaimer on every screen
- ✅ Fully accessible (WCAG 2.1 AA target) — works keyboard-only and with screen readers
- ✅ Works without JavaScript (progressive enhancement)
- ✅ Dark mode and reduced-motion support
- ✅ In-memory rate limiting + security headers
- ✅ Docker-ready, Cloud Run-deployable

---

## Architecture

```
User (browser)
      │
      ▼
 HTML Form (GET /)
      │  POST /analyze  (or POST /api/analyze for JSON)
      ▼
┌─────────────────────────────────────────┐
│  FastAPI App                            │
│  ┌─────────────┐  ┌────────────────┐   │
│  │  Validation │  │ Security       │   │
│  │  (Pydantic) │  │ (rate-limit,   │   │
│  └──────┬──────┘  │  headers)      │   │
│         │         └────────────────┘   │
│         ▼                              │
│  ┌──────────────┐                      │
│  │ Rules Engine │ ← reference_ranges.json │
│  │ (pure, O(n)) │                      │
│  └──────┬───────┘                      │
│         │ flagged values only          │
│         ▼                              │
│  ┌──────────────────────┐              │
│  │ Explainer            │              │
│  │  ┌───────────────┐   │              │
│  │  │ Gemini API    │──►│ LRU cache   │
│  │  │ (1 batch call)│   │             │
│  │  └───────┬───────┘   │             │
│  │    fail? │           │             │
│  │          ▼           │             │
│  │  ┌───────────────┐   │             │
│  │  │ Static        │   │             │
│  │  │ Fallback      │   │             │
│  │  └───────────────┘   │             │
│  └──────────────────────┘             │
│         │                             │
│         ▼                             │
│  ┌──────────────┐                     │
│  │ Jinja2 HTML  │  or  JSON response  │
│  │ (results.html│                     │
│  └──────────────┘                     │
└─────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| Backend | FastAPI + Uvicorn |
| Templates | Jinja2 (autoescaped) |
| Styling | Plain CSS (mobile-first, dark mode) |
| Scripting | Vanilla JS (progressive enhancement) |
| LLM | Google Gemini via `google-genai` SDK |
| Validation | Pydantic v2 |
| Testing | pytest + pytest-cov + httpx |
| Linting | ruff |

---

## How the Six Judging Criteria Are Addressed

### 🔒 Security
- No hardcoded secrets anywhere in code, tests, docs, or history
- API key read exclusively from environment variables
- Security headers on every response: CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy
- Jinja2 autoescape always on; `|safe` never used
- Rate limiter (20 req/min/IP) with safe X-Forwarded-For parsing
- Request body limited to 10 KB
- Global exception handler — never leaks stack traces
- Prompt injection structurally impossible: only validated enums and numbers reach the LLM

### 🧪 Testing
- ≥ 85% line coverage enforced in CI via `--cov-fail-under=85`
- Rules engine: boundary values, sex-specific ranges, one-sided bounds, critical thresholds, parametrized across all 14 tests
- Data integrity: JSON structure, ordering (critical_low < low < high < critical_high), fallback texts
- Schemas: rejects NaN, infinity, negatives, unknown IDs, extra fields, implausible values
- Explainer: mocked LLM, fallback paths, disallowed-phrase filtering, cache key determinism
- API: success paths, 422 validation, 429 rate limit, security headers, critical banner, disclaimer
- Security: no |safe in templates, .env in .gitignore, no hardcoded secrets

### ♿ Accessibility
- WCAG 2.1 AA target: 4.5:1 contrast, semantic landmarks, one h1 per page
- Every input has a `<label for="…">` binding and `aria-describedby` help text
- Status badges use text + symbol (never colour alone): "⬇ Low", "✓ Normal", "⬆⬆ Critical High"
- Skip-to-content link, visible focus outlines, no keyboard traps
- Results table: `<caption>`, `<th scope="col">`, `<th scope="row">`
- `prefers-reduced-motion` and `prefers-color-scheme` respected
- 44 × 44 px minimum touch targets

### ⚡ Efficiency
- Reference data loaded and validated **once at startup** (module-level)
- Rules engine is O(n) with dictionary lookups
- **One batched LLM call** per request, only for flagged values
- **LRU cache** keyed by (test_id, status) set — repeated identical requests don't re-hit the API
- GZip middleware for responses ≥ 500 bytes
- Static files served with cache headers
- Docker image based on `python:3.11-slim` — no dev tools, no cache artifacts

### 🏥 Problem Statement Alignment
- Directly addresses healthcare accessibility and health literacy
- Educational (not diagnostic) — cannot replace professional medical advice
- Scalable: Cloud Run autoscales to zero, stateless, containerised
- Socially relevant: targets the billions of people who receive lab results they cannot understand

### 💻 Code Quality
- Type hints on every function signature
- Google-style docstrings on all public functions and classes
- Functions kept under ~30 lines; no deep nesting
- Custom domain exceptions (`UnknownTestError`, `LabLensError`)
- Structured logging — never logs health data
- ruff-clean: rules E, F, I, B, UP, S, C4, SIM

---

## Setup & Local Development

### Prerequisites

- Python 3.11+
- A Google Gemini API key ([get one at ai.google.dev](https://ai.google.dev))

### Install

```bash
git clone https://github.com/YOUR_USERNAME/lablens.git
cd lablens
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
```

### Configure

```bash
cp .env.example .env
# Edit .env and set your GEMINI_API_KEY
```

### Run

```bash
uvicorn app.main:app --reload
# Open http://localhost:8000
```

### Run with Docker

```bash
docker build -t lablens .
docker run -p 8080:8080 -e GEMINI_API_KEY=your-key-here lablens
# Open http://localhost:8080
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GEMINI_API_KEY` | No* | — | Google Gemini API key. App works without it (fallback mode). |
| `GEMINI_MODEL` | No | `gemini-2.0-flash` | Gemini model name |
| `APP_ENV` | No | `development` | Set to `production` to disable /docs |
| `CORS_ORIGINS` | No | (same-origin) | Comma-separated allowed origins |
| `RATE_LIMIT_RPM` | No | `20` | Requests per minute per IP |

*Without `GEMINI_API_KEY`, the app works in fallback mode with static explanations.

---

## Running Tests & Coverage

```bash
# Activate venv first
pytest
# OR with explicit coverage:
pytest --cov=app --cov-report=term-missing --cov-report=html
# View HTML report:
open htmlcov/index.html
```

The test suite enforces ≥ 85% coverage automatically.

---

## Linting

```bash
ruff check .
ruff format --check .
# Auto-fix:
ruff check . --fix
ruff format .
```

---

## Deployment

See [DEPLOY.md](DEPLOY.md) for full Cloud Run deployment instructions.

---

## Medical Disclaimer

> ⚠️ **This tool is for educational purposes only and is not medical advice. Reference ranges vary between laboratories. Always consult a qualified healthcare professional about your results.**

LabLens does not diagnose, treat, or prescribe. It does not name your condition, suggest medications, or provide dosages. It is an educational tool to help you have better conversations with your doctor.

---

## Data Sources & Limitations

- Reference ranges are sourced from **MedlinePlus** (medlineplus.gov) and **Mayo Clinic Laboratories** (mayocliniclabs.com).
- Ranges reflect **general adult values** (18–64). Paediatric, geriatric, and pregnancy-specific ranges are not included.
- Individual laboratory reference intervals vary by equipment, methodology, reagents, and population — always compare your results against your own laboratory's reference range.
- LabLens is **not a diagnostic tool** and cannot account for your individual clinical history.

---

## Future Improvements

- Age-specific reference ranges (paediatric, senior)
- Multilingual support (Hindi, Spanish, Mandarin)
- PDF upload with OCR to auto-extract values
- More tests: complete metabolic panel, thyroid antibodies, iron studies
- Trend tracking (compare results over time, with local storage only)
- Clinician-facing mode with denser information
- Offline-first PWA support
