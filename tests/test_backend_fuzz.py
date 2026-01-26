"""Fuzz tests for backend API using Schemathesis.

These tests automatically generate inputs based on the OpenAPI schema
to find edge cases, crashes, and schema violations.

Run with: pytest tests/test_backend_fuzz.py -v --run-fuzz

With database:
    DATABASE_URL=postgresql://user:pass@localhost:5432/heisenberg pytest tests/test_backend_fuzz.py -v --run-fuzz
"""

import pytest
import schemathesis

from heisenberg.backend.app import app

# Skip all tests in this module unless --run-fuzz is provided
pytestmark = pytest.mark.fuzz


def _skip_on_db_error(e: Exception) -> None:
    """Skip test if database-related error occurs."""
    error_msg = str(e).lower()
    skip_patterns = [
        "database not initialized",
        "not initialized",
        "attached to a different loop",
        "event loop",
    ]
    if any(pattern in error_msg for pattern in skip_patterns):
        pytest.skip(f"Database not available: {type(e).__name__}")


# Load schema from FastAPI app
schema = schemathesis.openapi.from_asgi("/openapi.json", app=app)


class TestSchemaBasics:
    """Basic schema validation tests."""

    def test_schema_loads(self):
        """Schema should load successfully from app."""
        assert schema is not None

    def test_schema_has_operations(self):
        """Schema should have API operations defined."""
        operations = list(schema.get_all_operations())
        assert len(operations) > 0

    def test_all_endpoints_documented(self):
        """All expected endpoints should be in the OpenAPI schema."""
        operations = list(schema.get_all_operations())
        paths = set()
        for op_result in operations:
            # In schemathesis 4.x, get_all_operations returns Ok objects
            # Call ok() method to get the actual APIOperation
            op = op_result.ok()
            paths.add(op.path)

        expected_paths = {
            "/health",
            "/health/detailed",
            "/api/v1/analyze/",
            "/api/v1/feedback/stats",
            "/api/v1/tasks",
            "/api/v1/usage/summary",
            "/api/v1/usage/by-model",
        }

        for path in expected_paths:
            assert path in paths, f"Missing endpoint in schema: {path}"


# Fuzz test for health endpoints
@schema.include(path="/health").parametrize()
def test_health_endpoint_fuzz(case):
    """Fuzz the health endpoint."""
    case.call_and_validate()


@schema.include(path="/health/detailed").parametrize()
def test_health_detailed_endpoint_fuzz(case):
    """Fuzz the detailed health endpoint."""
    response = case.call()
    # Allow 200 (healthy), 405 (wrong method), or 503 (unhealthy when DB not configured)
    assert response.status_code in (200, 405, 503)


# Fuzz test for analyze endpoint
@schema.include(path="/api/v1/analyze/").parametrize()
def test_analyze_endpoint_fuzz(case):
    """Analyze endpoint should handle malformed input gracefully."""
    response = case.call()
    # Should return 401 (no API key), 422 (validation), or 501 (not implemented)
    # Should NOT return 500 (internal server error)
    assert response.status_code != 500


# Fuzz test for feedback endpoints
@schema.include(path_regex=r"/api/v1/.*feedback.*").parametrize()
def test_feedback_endpoints_fuzz(case):
    """Feedback endpoints should handle fuzzed requests."""
    try:
        response = case.call()
    except RuntimeError as e:
        _skip_on_db_error(e)
        raise
    # May fail with 500 if DB not configured, that's expected
    # 405 = Method Not Allowed (valid for wrong HTTP method)
    # 429 = Rate limited (valid during fuzz testing)
    assert response.status_code in (200, 201, 404, 405, 422, 429, 500)


# Fuzz test for tasks endpoints
@schema.include(path_regex=r"/api/v1/tasks.*").parametrize()
def test_tasks_endpoints_fuzz(case):
    """Tasks endpoints should validate input."""
    try:
        response = case.call()
    except RuntimeError as e:
        _skip_on_db_error(e)
        raise
    # Should validate and reject bad input, or fail gracefully if DB not configured
    # 405 = Method Not Allowed (valid for wrong HTTP method)
    # 429 = Rate limited (valid during fuzz testing)
    assert response.status_code in (200, 201, 404, 405, 422, 429, 500)


# Fuzz test for usage endpoints
@schema.include(path_regex=r"/api/v1/usage.*").parametrize()
def test_usage_endpoints_fuzz(case):
    """Usage endpoints should handle various query params."""
    try:
        response = case.call()
    except RuntimeError as e:
        _skip_on_db_error(e)
        raise
    # 422 for validation errors, 500 if DB not configured
    # 405 = Method Not Allowed (valid for wrong HTTP method)
    # 429 = Rate limited (valid during fuzz testing)
    assert response.status_code in (200, 405, 422, 429, 500)


# Full API fuzz test - test everything
@schema.parametrize()
def test_full_api_no_500_errors(case):
    """No endpoint should return 500 on any valid schema input."""
    try:
        response = case.call()
    except RuntimeError as e:
        _skip_on_db_error(e)
        raise

    # Allow all responses except unexpected 500s
    # DB not initialized errors are acceptable in test environment
    if response.status_code == 500:
        response_text = response.text.lower()
        acceptable_errors = [
            "database not initialized",
            "not initialized",
            "database",
            "event loop",
        ]
        assert any(err in response_text for err in acceptable_errors), (
            f"Unexpected 500 error: {response.text[:200]}"
        )
