"""Tests for backend API endpoints - TDD for Phase 4."""

import pytest
from httpx import ASGITransport, AsyncClient


class TestAPIApp:
    """Test suite for FastAPI application."""

    def test_app_exists(self):
        """FastAPI app should be importable."""
        from heisenberg.backend.app import app

        assert app is not None

    def test_app_has_title(self):
        """App should have a title."""
        from heisenberg.backend.app import app

        assert app.title == "Heisenberg API"

    def test_app_has_version(self):
        """App should have a version."""
        from heisenberg.backend.app import app

        assert app.version is not None


class TestHealthEndpoint:
    """Test suite for health check endpoint."""

    @pytest.fixture
    def test_client(self):
        """Create test client without database."""
        from heisenberg.backend.app import app

        return AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        )

    @pytest.mark.asyncio
    async def test_health_endpoint_exists(self, test_client: AsyncClient):
        """Health endpoint should return 200."""
        async with test_client as client:
            response = await client.get("/health")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_health_returns_status(self, test_client: AsyncClient):
        """Health endpoint should return status."""
        async with test_client as client:
            response = await client.get("/health")
            data = response.json()
            assert "status" in data
            assert data["status"] == "healthy"


class TestAnalyzeEndpointSchema:
    """Test suite for /api/v1/analyze endpoint schemas."""

    def test_analyze_request_schema_exists(self):
        """AnalyzeRequest schema should be importable."""
        from heisenberg.backend.schemas import AnalyzeRequest

        assert AnalyzeRequest is not None

    def test_analyze_request_has_required_fields(self):
        """AnalyzeRequest should have required fields."""
        from heisenberg.backend.schemas import AnalyzeRequest

        # Check model fields
        fields = AnalyzeRequest.model_fields
        assert "repository" in fields
        assert "failed_tests" in fields

    def test_analyze_response_schema_exists(self):
        """AnalyzeResponse schema should be importable."""
        from heisenberg.backend.schemas import AnalyzeResponse

        assert AnalyzeResponse is not None

    def test_failed_test_schema_exists(self):
        """FailedTest schema should be importable."""
        from heisenberg.backend.schemas import FailedTest

        assert FailedTest is not None

    def test_diagnosis_response_schema_exists(self):
        """DiagnosisResponse schema should be importable."""
        from heisenberg.backend.schemas import DiagnosisResponse

        assert DiagnosisResponse is not None


class TestAuthenticationSchema:
    """Test suite for authentication schemas and utilities."""

    def test_api_key_header_dependency_exists(self):
        """API key header dependency should be importable."""
        from heisenberg.backend.auth import get_api_key

        assert get_api_key is not None

    def test_api_key_hasher_exists(self):
        """API key hasher should be importable."""
        from heisenberg.backend.auth import hash_api_key, verify_api_key

        assert hash_api_key is not None
        assert verify_api_key is not None

    def test_api_key_hashing_works(self):
        """API key hashing should produce consistent results."""
        from heisenberg.backend.auth import hash_api_key, verify_api_key

        key = "test-api-key-12345"
        hashed = hash_api_key(key)

        assert hashed != key  # Should be hashed
        assert verify_api_key(key, hashed)  # Should verify

    def test_api_key_verification_fails_for_wrong_key(self):
        """API key verification should fail for wrong key."""
        from heisenberg.backend.auth import hash_api_key, verify_api_key

        key = "test-api-key-12345"
        wrong_key = "wrong-api-key"
        hashed = hash_api_key(key)

        assert not verify_api_key(wrong_key, hashed)

    def test_generate_api_key_exists(self):
        """API key generator should be importable."""
        from heisenberg.backend.auth import generate_api_key

        assert generate_api_key is not None

    def test_generate_api_key_returns_string(self):
        """API key generator should return a string."""
        from heisenberg.backend.auth import generate_api_key

        key = generate_api_key()
        assert isinstance(key, str)
        assert len(key) > 20  # Should be reasonably long
