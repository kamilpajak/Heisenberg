"""Tests for /api/v1/analyze endpoint - TDD for Phase 4."""

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient


class TestAnalyzeEndpoint:
    """Test suite for the analyze endpoint."""

    @pytest.fixture
    def test_client(self):
        """Create test client."""
        from heisenberg.backend.app import app

        return AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        )

    @pytest.fixture
    def valid_analyze_request(self):
        """Valid analyze request payload."""
        return {
            "repository": "owner/repo",
            "commit_sha": "abc123def456",
            "branch": "main",
            "total_tests": 10,
            "passed_tests": 8,
            "failed_tests": [
                {
                    "title": "Login test should work",
                    "file": "tests/login.spec.ts",
                    "suite": "Authentication",
                    "duration_ms": 5000,
                    "errors": [
                        {
                            "message": "TimeoutError: waiting for selector",
                            "stack": "at LoginPage.login (login.ts:10)",
                        }
                    ],
                }
            ],
            "skipped_tests": 1,
        }

    @pytest.mark.asyncio
    async def test_analyze_endpoint_exists(self, test_client: AsyncClient):
        """Analyze endpoint should exist at /api/v1/analyze/."""
        async with test_client as client:
            # Without API key, should get 401
            response = await client.post("/api/v1/analyze/", json={})
            assert response.status_code in (401, 422)  # Unauthorized or validation error

    @pytest.mark.asyncio
    async def test_analyze_requires_api_key(
        self, test_client: AsyncClient, valid_analyze_request: dict
    ):
        """Analyze endpoint should require API key."""
        async with test_client as client:
            response = await client.post("/api/v1/analyze/", json=valid_analyze_request)
            assert response.status_code == 401
            assert (
                "API key" in response.json().get("detail", "").lower()
                or "missing" in response.json().get("detail", "").lower()
            )

    @pytest.mark.asyncio
    async def test_analyze_validates_request_body(self, test_client: AsyncClient):
        """Analyze endpoint should validate request body."""
        async with test_client as client:
            response = await client.post(
                "/api/v1/analyze/",
                json={"invalid": "data"},
                headers={"X-API-Key": "test-key"},
            )
            # Should be 422 Unprocessable Entity for invalid body
            assert response.status_code == 422


class TestAnalyzeService:
    """Test suite for the analyze service layer."""

    def test_analyze_service_exists(self):
        """AnalyzeService should be importable."""
        from heisenberg.backend.services.analyze import AnalyzeService

        assert AnalyzeService is not None

    @pytest.mark.asyncio
    async def test_analyze_service_processes_request(self):
        """AnalyzeService should process analyze requests."""
        from heisenberg.backend.schemas import AnalyzeRequest, FailedTest, TestError
        from heisenberg.backend.services.analyze import AnalyzeService

        # Create a mock LLM client
        mock_llm = AsyncMock()
        mock_llm.analyze.return_value = AsyncMock(
            content="""## Root Cause Analysis
Database connection timeout.

## Evidence
- Error shows timeout
- Logs show connection refused

## Suggested Fix
Check database connection settings.

## Confidence Score
HIGH (85%) - Clear correlation.""",
            input_tokens=100,
            output_tokens=200,
        )

        service = AnalyzeService(llm_client=mock_llm)

        request = AnalyzeRequest(
            repository="owner/repo",
            failed_tests=[
                FailedTest(
                    title="Test 1",
                    file="test.ts",
                    errors=[TestError(message="Timeout error")],
                )
            ],
        )

        result = await service.analyze(request)

        assert result is not None
        assert len(result.diagnoses) == 1
        assert result.diagnoses[0].test_name == "Test 1"

    @pytest.mark.asyncio
    async def test_analyze_service_handles_multiple_failures(self):
        """AnalyzeService should analyze all failures in single LLM call."""
        from heisenberg.backend.schemas import AnalyzeRequest, FailedTest, TestError
        from heisenberg.backend.services.analyze import AnalyzeService

        mock_llm = AsyncMock()
        mock_llm.analyze.return_value = AsyncMock(
            content="""## Root Cause Analysis
Test issue.

## Evidence
- Evidence here

## Suggested Fix
Fix here.

## Confidence Score
MEDIUM (60%)""",
            input_tokens=100,
            output_tokens=200,
        )

        service = AnalyzeService(llm_client=mock_llm)

        request = AnalyzeRequest(
            repository="owner/repo",
            failed_tests=[
                FailedTest(title="Test 1", errors=[TestError(message="Error 1")]),
                FailedTest(title="Test 2", errors=[TestError(message="Error 2")]),
            ],
        )

        result = await service.analyze(request)

        # Single diagnosis covers all failures (better context, lower cost)
        assert len(result.diagnoses) == 1
        assert result.diagnoses[0].test_name == "2 failed tests"
        # Verify single LLM call (not N calls)
        assert mock_llm.analyze.call_count == 1


class TestAnalyzeRouter:
    """Test suite for the analyze API router."""

    def test_router_exists(self):
        """Analyze router should be importable."""
        from heisenberg.backend.routers.analyze import router

        assert router is not None

    def test_router_has_analyze_endpoint(self):
        """Router should have POST /analyze endpoint."""
        from heisenberg.backend.routers.analyze import router

        routes = [r.path for r in router.routes]
        # Router path is "/" relative to its prefix "/analyze"
        assert "/" in routes or "/analyze/" in routes
