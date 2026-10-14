"""Shared test fixtures for the LabLens test suite."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture(scope="session")
def app():
    """Create a test FastAPI application instance."""
    return create_app()


@pytest.fixture(scope="session")
def client(app):
    """Create a TestClient for the FastAPI app."""
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def valid_payload():
    """A valid analysis request payload with common test values."""
    return {
        "sex": "male",
        "values": {
            "hemoglobin": 15.0,
            "wbc": 6.5,
            "platelets": 250.0,
            "fasting_glucose": 85.0,
        },
    }


@pytest.fixture
def flagged_payload():
    """A payload that will produce flagged (abnormal) results."""
    return {
        "sex": "male",
        "values": {
            "hemoglobin": 8.0,  # LOW for male (< 13.5)
            "fasting_glucose": 120.0,  # HIGH (> 99)
        },
    }


@pytest.fixture
def critical_payload():
    """A payload that will produce critical results."""
    return {
        "sex": "male",
        "values": {
            "hemoglobin": 5.0,  # CRITICAL_LOW for male (< 7.0)
            "fasting_glucose": 600.0,  # CRITICAL_HIGH (> 500)
        },
    }
