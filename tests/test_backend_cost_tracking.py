"""Tests for LLM cost tracking - TDD for Phase 6."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient


class TestUsageRecordModel:
    """Test suite for UsageRecord model."""

    def test_usage_record_model_exists(self):
        """UsageRecord model should be importable."""
        from heisenberg.backend.models import UsageRecord

        assert UsageRecord is not None

    def test_usage_record_has_required_fields(self):
        """UsageRecord model should have required fields."""
        from heisenberg.backend.models import UsageRecord

        columns = {c.name for c in UsageRecord.__table__.columns}
        assert "id" in columns
        assert "organization_id" in columns
        assert "analysis_id" in columns
        assert "model_name" in columns
        assert "input_tokens" in columns
        assert "output_tokens" in columns
        assert "cost_usd" in columns
        assert "created_at" in columns

    def test_usage_record_relates_to_organization(self):
        """UsageRecord should have relationship to Organization."""
        from heisenberg.backend.models import UsageRecord

        assert hasattr(UsageRecord, "organization")

    def test_usage_record_relates_to_analysis(self):
        """UsageRecord should have relationship to Analysis."""
        from heisenberg.backend.models import UsageRecord

        assert hasattr(UsageRecord, "analysis")


class TestCostCalculator:
    """Test suite for cost calculation."""

    def test_cost_calculator_exists(self):
        """CostCalculator should be importable."""
        from heisenberg.backend.cost_tracking import CostCalculator

        assert CostCalculator is not None

    def test_calculate_cost_claude_sonnet(self):
        """Should calculate cost for Claude Sonnet correctly."""
        from heisenberg.backend.cost_tracking import CostCalculator

        calc = CostCalculator()
        # Claude 3.5 Sonnet: $3/1M input, $15/1M output
        cost = calc.calculate_cost(
            model_name="claude-3-5-sonnet-20241022",
            input_tokens=1000,
            output_tokens=500,
        )
        expected = (1000 * 3 / 1_000_000) + (500 * 15 / 1_000_000)
        assert abs(cost - Decimal(str(expected))) < Decimal("0.0001")

    def test_calculate_cost_unknown_model_returns_zero(self):
        """Should return zero cost for unknown models."""
        from heisenberg.backend.cost_tracking import CostCalculator

        calc = CostCalculator()
        cost = calc.calculate_cost(
            model_name="unknown-model",
            input_tokens=1000,
            output_tokens=500,
        )
        assert cost == Decimal("0")

    def test_supported_models_list(self):
        """CostCalculator should list supported models."""
        from heisenberg.backend.cost_tracking import CostCalculator

        calc = CostCalculator()
        models = calc.supported_models
        assert "claude-3-5-sonnet-20241022" in models
        assert "gpt-4o" in models
        assert "gpt-4o-mini" in models


class TestUsageSchemas:
    """Test suite for usage tracking schemas."""

    def test_usage_create_schema_exists(self):
        """UsageCreate schema should be importable."""
        from heisenberg.backend.schemas import UsageCreate

        assert UsageCreate is not None

    def test_usage_summary_schema_exists(self):
        """UsageSummary schema should be importable."""
        from heisenberg.backend.schemas import UsageSummary

        assert UsageSummary is not None

    def test_usage_summary_has_fields(self):
        """UsageSummary should have expected fields."""
        from heisenberg.backend.schemas import UsageSummary

        summary = UsageSummary(
            organization_id=uuid.uuid4(),
            period_start=datetime.now(UTC),
            period_end=datetime.now(UTC),
            total_requests=100,
            total_input_tokens=50000,
            total_output_tokens=25000,
            total_cost_usd=Decimal("1.50"),
            by_model={"claude-3-5-sonnet": {"requests": 100, "cost_usd": "1.50"}},
        )
        assert summary.total_requests == 100
        assert summary.total_cost_usd == Decimal("1.50")


class TestUsageEndpoints:
    """Test suite for usage tracking endpoints."""

    @pytest.mark.asyncio
    async def test_usage_summary_endpoint_exists(self):
        """GET /api/v1/usage/summary should exist."""
        from fastapi import FastAPI

        from heisenberg.backend.database import get_db
        from heisenberg.backend.routers import usage

        app = FastAPI()
        app.include_router(usage.router, prefix="/api/v1")

        # Mock the aggregate result row
        mock_agg_row = MagicMock()
        mock_agg_row.total_requests = 0
        mock_agg_row.total_input_tokens = 0
        mock_agg_row.total_output_tokens = 0
        mock_agg_row.total_cost_usd = Decimal("0")

        mock_agg_result = MagicMock()
        mock_agg_result.one.return_value = mock_agg_row

        mock_model_result = MagicMock()
        mock_model_result.all.return_value = []

        mock_session = AsyncMock()
        # First call returns aggregate, second returns by-model
        mock_session.execute = AsyncMock(side_effect=[mock_agg_result, mock_model_result])

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/usage/summary",
                params={"organization_id": str(uuid.uuid4())},
            )
            # Should return 200
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_usage_by_model_endpoint_exists(self):
        """GET /api/v1/usage/by-model should exist."""
        from fastapi import FastAPI

        from heisenberg.backend.database import get_db
        from heisenberg.backend.routers import usage

        app = FastAPI()
        app.include_router(usage.router, prefix="/api/v1")

        mock_result = MagicMock()
        mock_result.all.return_value = []

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/usage/by-model",
                params={"organization_id": str(uuid.uuid4())},
            )
            assert response.status_code != 404


class TestBudgetAlerts:
    """Test suite for budget alert functionality."""

    def test_budget_alert_settings_exists(self):
        """Settings should have budget alert fields."""
        from heisenberg.backend.config import Settings

        settings = Settings(
            database_url="postgresql://test:test@localhost/test",
            secret_key="test-secret-key",
        )
        assert hasattr(settings, "budget_alert_threshold_usd")
        assert settings.budget_alert_threshold_usd is None  # default no alert

    def test_budget_alert_can_be_set(self):
        """Budget alert threshold can be set."""
        from heisenberg.backend.config import Settings

        settings = Settings(
            database_url="postgresql://test:test@localhost/test",
            secret_key="test-secret-key",
            budget_alert_threshold_usd=100.0,
        )
        assert settings.budget_alert_threshold_usd == pytest.approx(100.0)

    def test_check_budget_alert_function_exists(self):
        """check_budget_alert function should exist."""
        from heisenberg.backend.cost_tracking import check_budget_alert

        assert check_budget_alert is not None

    def test_check_budget_alert_returns_status(self):
        """check_budget_alert should return alert status."""
        from heisenberg.backend.cost_tracking import check_budget_alert

        result = check_budget_alert(
            current_spend=Decimal("50.00"),
            threshold=Decimal("100.00"),
        )
        assert not result["alert"]
        assert result["percentage"] == pytest.approx(50.0)

    def test_check_budget_alert_triggers_at_threshold(self):
        """check_budget_alert should trigger at threshold."""
        from heisenberg.backend.cost_tracking import check_budget_alert

        result = check_budget_alert(
            current_spend=Decimal("100.00"),
            threshold=Decimal("100.00"),
        )
        assert result["alert"]
        assert result["percentage"] == pytest.approx(100.0)


class TestOrganizationUsageRelation:
    """Test suite for Organization-UsageRecord relationship."""

    def test_organization_has_usage_records_relation(self):
        """Organization model should have usage_records relationship."""
        from heisenberg.backend.models import Organization

        assert hasattr(Organization, "usage_records")

    def test_usage_record_cascades_on_organization_delete(self):
        """UsageRecord should be deleted when Organization is deleted."""
        from heisenberg.backend.models import Organization

        usage_rel = Organization.__mapper__.relationships.get("usage_records")
        assert usage_rel is not None
        assert "delete-orphan" in usage_rel.cascade


class TestUsageMigration:
    """Test suite for usage tracking migration."""

    def test_usage_migration_exists(self):
        """Usage tracking migration file should exist."""
        from pathlib import Path

        project_root = Path(__file__).parent.parent
        migrations_dir = project_root / "migrations" / "versions"

        if not migrations_dir.exists():
            pytest.skip("Migrations directory not available")

        migration_files = list(migrations_dir.glob("*usage*.py"))
        assert len(migration_files) >= 1, "Usage tracking migration not found"

    def test_usage_migration_has_upgrade(self):
        """Usage migration should have upgrade function."""
        import importlib.util
        from pathlib import Path

        project_root = Path(__file__).parent.parent
        migrations_dir = project_root / "migrations" / "versions"

        if not migrations_dir.exists():
            pytest.skip("Migrations directory not available")

        migration_files = list(migrations_dir.glob("*usage*.py"))
        assert len(migration_files) >= 1

        spec = importlib.util.spec_from_file_location("usage_migration", migration_files[0])
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert hasattr(module, "upgrade")
        assert callable(module.upgrade)
