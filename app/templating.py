"""Jinja2 template configuration for LabLens."""

from __future__ import annotations

from pathlib import Path

from fastapi.templating import Jinja2Templates

# Base templates directory relative to this module.
_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

# Shared Jinja2Templates instance with autoescape enabled by default.
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
