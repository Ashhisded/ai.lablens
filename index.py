"""Vercel serverless entrypoint for LabLens."""

from __future__ import annotations

from app.main import app

__all__ = ["app"]
