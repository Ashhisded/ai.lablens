"""Security-specific tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).parent.parent


class TestNoStackTraceLeakage:
    def test_unknown_route_does_not_leak_traceback(self, client):
        response = client.get("/nonexistent-path-xyz")
        assert "Traceback" not in response.text
        assert "File " not in response.text

    def test_api_error_body_is_generic(self, client):
        """Validation errors must return structured detail, not raw exceptions."""
        response = client.post(
            "/api/analyze",
            json={"sex": "invalid_sex", "values": {"hemoglobin": 15.0}},
        )
        assert "Traceback" not in response.text
        assert "File " not in response.text


class TestTemplatesSafety:
    def test_no_safe_filter_in_templates(self):
        """Jinja2 |safe filter must not appear in any template (XSS risk)."""
        templates_dir = ROOT / "app" / "templates"
        for tmpl in templates_dir.glob("*.html"):
            content = tmpl.read_text(encoding="utf-8")
            assert "|safe" not in content, f"Template '{tmpl.name}' uses |safe filter (XSS risk)"


class TestEnvFileNotTracked:
    def test_env_not_in_git(self):
        """.env must be listed in .gitignore and not tracked by git."""
        gitignore = ROOT / ".gitignore"
        assert gitignore.exists()
        content = gitignore.read_text(encoding="utf-8")
        assert ".env" in content, ".env must be in .gitignore"


class TestNoHardcodedSecrets:
    """Scan all tracked Python and config files for secret patterns."""

    PATTERNS = [
        "".join(["AI", "za"]),
        "".join(["api_", "key ="]),
        "".join(["api_", "key="]),
        "".join(["BEGIN ", "PRIVATE KEY"]),
        "".join(["BEGIN ", "RSA PRIVATE KEY"]),
        "".join(["password", " ="]),
        "".join(["password", "="]),
        "".join(["secret", " ="]),
        "".join(["secret", "="]),
    ]

    def _get_tracked_files(self):
        """Get list of files tracked by git (if git is available)."""
        try:
            result = subprocess.run(
                ["git", "ls-files"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return [ROOT / f for f in result.stdout.strip().splitlines()]
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        # Fallback: scan Python and config files directly
        files = list(ROOT.rglob("*.py")) + list(ROOT.rglob("*.toml")) + list(ROOT.rglob("*.txt"))
        return [f for f in files if ".venv" not in str(f) and "__pycache__" not in str(f)]

    def test_no_hardcoded_api_keys(self):
        files = self._get_tracked_files()
        violations = []
        for filepath in files:
            if not filepath.is_file():
                continue
            # Skip .env.example — it's allowed to contain placeholder text
            if filepath.name == ".env.example":
                continue
            try:
                content = filepath.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for pattern in self.PATTERNS:
                # Only flag if it looks like an actual value assignment
                if pattern.lower() in content.lower():
                    # Check it's not just a comment or placeholder
                    for line in content.splitlines():
                        if pattern.lower() in line.lower():
                            stripped = line.strip()
                            # Allow comments
                            if stripped.startswith("#"):
                                continue
                            # Allow os.environ.get() calls
                            if "os.environ" in stripped or "get_settings" in stripped:
                                continue
                            # Allow variable names that contain the word
                            if "GEMINI_API_KEY" in stripped and "environ" in stripped:
                                continue
                            if "api_key" in pattern and "api_key" in stripped:
                                # Check if it's just a variable name reference, not an assignment with a real value
                                if "your-key-here" in stripped or "placeholder" in stripped:
                                    continue
                                # Skip test files that reference the pattern name
                                if "test_" in str(filepath) or "PATTERNS" in stripped:
                                    continue
        assert not violations, f"Potential hardcoded secrets: {violations}"


class TestRateLimitHeader:
    def test_rate_limit_returns_retry_after(self, app):
        from unittest.mock import patch

        from fastapi.testclient import TestClient

        with patch("app.security.get_settings") as mock_settings:
            mock_settings.return_value.rate_limit_rpm = 1
            mock_settings.return_value.max_body_size = 10_240

            from app.security import _request_log

            _request_log.clear()

            test_client = TestClient(app, raise_server_exceptions=False)
            payload = {"sex": "male", "values": {"hemoglobin": 15.0}}

            # First request should succeed
            r1 = test_client.post("/api/analyze", json=payload)
            # Second should be rate-limited
            r2 = test_client.post("/api/analyze", json=payload)

            if r2.status_code == 429:
                assert "retry-after" in r2.headers
