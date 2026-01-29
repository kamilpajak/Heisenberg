"""Tests for backend database models - TDD for Phase 4."""


class TestOrganizationModel:
    """Test suite for Organization database model."""

    def test_organization_model_exists(self):
        """Organization model should be importable."""
        from heisenberg.backend.models import Organization

        assert Organization is not None

    def test_organization_has_required_fields(self):
        """Organization should have id, name, and created_at fields."""
        from heisenberg.backend.models import Organization

        # Check that the model has the required columns
        columns = {c.name for c in Organization.__table__.columns}
        assert "id" in columns
        assert "name" in columns
        assert "created_at" in columns

    def test_organization_id_is_uuid(self):
        """Organization id should be UUID type."""
        from heisenberg.backend.models import Organization

        id_column = Organization.__table__.columns["id"]
        # SQLAlchemy UUID type
        assert "UUID" in str(id_column.type).upper() or "GUID" in str(id_column.type).upper()


class TestAPIKeyModel:
    """Test suite for API Key database model."""

    def test_api_key_model_exists(self):
        """APIKey model should be importable."""
        from heisenberg.backend.models import APIKey

        assert APIKey is not None

    def test_api_key_has_required_fields(self):
        """APIKey should have id, key_hash, organization_id, and created_at fields."""
        from heisenberg.backend.models import APIKey

        columns = {c.name for c in APIKey.__table__.columns}
        assert "id" in columns
        assert "key_hash" in columns
        assert "organization_id" in columns
        assert "created_at" in columns
        assert "is_active" in columns

    def test_api_key_has_organization_relationship(self):
        """APIKey should have a relationship to Organization."""
        from heisenberg.backend.models import APIKey

        assert hasattr(APIKey, "organization")


class TestTestRunModel:
    """Test suite for TestRun database model."""

    def test_test_run_model_exists(self):
        """TestRun model should be importable."""
        from heisenberg.backend.models import TestRun

        assert TestRun is not None

    def test_test_run_has_required_fields(self):
        """TestRun should have fields for test execution data."""
        from heisenberg.backend.models import TestRun

        columns = {c.name for c in TestRun.__table__.columns}
        assert "id" in columns
        assert "organization_id" in columns
        assert "repository" in columns
        assert "commit_sha" in columns
        assert "branch" in columns
        assert "total_tests" in columns
        assert "failed_tests" in columns
        assert "created_at" in columns

    def test_test_run_has_organization_relationship(self):
        """TestRun should have a relationship to Organization."""
        from heisenberg.backend.models import TestRun

        assert hasattr(TestRun, "organization")


class TestAnalysisModel:
    """Test suite for Analysis database model."""

    def test_analysis_model_exists(self):
        """Analysis model should be importable."""
        from heisenberg.backend.models import Analysis

        assert Analysis is not None

    def test_analysis_has_required_fields(self):
        """Analysis should have fields for AI analysis results."""
        from heisenberg.backend.models import Analysis

        columns = {c.name for c in Analysis.__table__.columns}
        assert "id" in columns
        assert "test_run_id" in columns
        assert "test_name" in columns
        assert "error_message" in columns
        assert "root_cause" in columns
        assert "confidence" in columns
        assert "suggested_fix" in columns
        assert "input_tokens" in columns
        assert "output_tokens" in columns
        assert "created_at" in columns

    def test_analysis_has_test_run_relationship(self):
        """Analysis should have a relationship to TestRun."""
        from heisenberg.backend.models import Analysis

        assert hasattr(Analysis, "test_run")


class TestDatabaseBase:
    """Test suite for database base configuration."""

    def test_base_model_exists(self):
        """Base model should be importable."""
        from heisenberg.backend.models import Base

        assert Base is not None

    def test_all_models_inherit_from_base(self):
        """All models should inherit from Base."""
        from heisenberg.backend.models import Analysis, APIKey, Base, Organization, TestRun

        assert issubclass(Organization, Base)
        assert issubclass(APIKey, Base)
        assert issubclass(TestRun, Base)
        assert issubclass(Analysis, Base)
