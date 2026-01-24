"""Tests for feedback loop functionality - TDD for Phase 6."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient


class TestFeedbackModel:
    """Test suite for Feedback model."""

    def test_feedback_model_exists(self):
        """Feedback model should be importable."""
        from heisenberg.backend.models import Feedback

        assert Feedback is not None

    def test_feedback_has_required_fields(self):
        """Feedback model should have required fields."""
        from heisenberg.backend.models import Feedback

        # Check that the model has expected columns
        columns = {c.name for c in Feedback.__table__.columns}
        assert "id" in columns
        assert "analysis_id" in columns
        assert "is_helpful" in columns
        assert "comment" in columns
        assert "created_at" in columns

    def test_feedback_relates_to_analysis(self):
        """Feedback should have relationship to Analysis."""
        from heisenberg.backend.models import Feedback

        # Check relationship exists
        assert hasattr(Feedback, "analysis")


class TestFeedbackSchemas:
    """Test suite for Feedback schemas."""

    def test_feedback_create_schema_exists(self):
        """FeedbackCreate schema should be importable."""
        from heisenberg.backend.schemas import FeedbackCreate

        assert FeedbackCreate is not None

    def test_feedback_create_requires_is_helpful(self):
        """FeedbackCreate should require is_helpful field."""
        from heisenberg.backend.schemas import FeedbackCreate

        feedback = FeedbackCreate(is_helpful=True)
        assert feedback.is_helpful

    def test_feedback_create_optional_comment(self):
        """FeedbackCreate should have optional comment."""
        from heisenberg.backend.schemas import FeedbackCreate

        feedback = FeedbackCreate(is_helpful=False, comment="Not accurate")
        assert feedback.comment == "Not accurate"

        feedback_no_comment = FeedbackCreate(is_helpful=True)
        assert feedback_no_comment.comment is None

    def test_feedback_response_schema_exists(self):
        """FeedbackResponse schema should be importable."""
        from heisenberg.backend.schemas import FeedbackResponse

        assert FeedbackResponse is not None

    def test_feedback_response_has_fields(self):
        """FeedbackResponse should have expected fields."""
        from heisenberg.backend.schemas import FeedbackResponse

        response = FeedbackResponse(
            id=uuid.uuid4(),
            analysis_id=uuid.uuid4(),
            is_helpful=True,
            comment=None,
            created_at=datetime.now(UTC),
        )
        assert response.id is not None
        assert response.is_helpful


class TestFeedbackEndpoint:
    """Test suite for feedback API endpoint."""

    @pytest.mark.asyncio
    async def test_feedback_endpoint_exists(self):
        """POST /api/v1/analyses/{id}/feedback should exist."""
        from unittest.mock import patch

        from fastapi import FastAPI

        from heisenberg.backend.routers import feedback

        app = FastAPI()
        app.include_router(feedback.router, prefix="/api/v1")

        # Mock the get_db_session to avoid database connection
        with patch.object(feedback, "get_db_session") as mock_get_db:
            mock_session = AsyncMock()
            mock_session.get = AsyncMock(return_value=None)  # Analysis not found
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                # Should not return 404 for missing route (404 for missing analysis is ok)
                response = await client.post(
                    f"/api/v1/analyses/{uuid.uuid4()}/feedback",
                    json={"is_helpful": True},
                )
                # 404 for "analysis not found" is expected, not for "route not found"
                assert response.status_code == 404
                assert "Analysis" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_feedback_requires_valid_analysis_id(self):
        """Feedback should return 404 for non-existent analysis."""
        from unittest.mock import patch

        from fastapi import FastAPI

        from heisenberg.backend.routers import feedback

        app = FastAPI()
        app.include_router(feedback.router, prefix="/api/v1")

        # Mock the database session
        with patch.object(feedback, "get_db_session") as mock_get_db:
            mock_session = AsyncMock()
            mock_session.get = AsyncMock(return_value=None)  # Analysis not found
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    f"/api/v1/analyses/{uuid.uuid4()}/feedback",
                    json={"is_helpful": True},
                )
                assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_feedback_creates_record(self):
        """Feedback should create a record in database."""
        from unittest.mock import patch

        from fastapi import FastAPI

        from heisenberg.backend.models import Analysis
        from heisenberg.backend.routers import feedback

        app = FastAPI()
        app.include_router(feedback.router, prefix="/api/v1")

        analysis_id = uuid.uuid4()
        feedback_id = uuid.uuid4()
        mock_analysis = MagicMock(spec=Analysis)
        mock_analysis.id = analysis_id

        with patch.object(feedback, "get_db_session") as mock_get_db:
            mock_session = AsyncMock()
            mock_session.get = AsyncMock(return_value=mock_analysis)

            # Capture added feedback and set ID/created_at on refresh
            captured_feedback = None

            def capture_add(fb):
                nonlocal captured_feedback
                captured_feedback = fb

            async def mock_refresh(fb):
                fb.id = feedback_id
                fb.created_at = datetime.now(UTC)

            mock_session.add = MagicMock(side_effect=capture_add)
            mock_session.commit = AsyncMock()
            mock_session.refresh = AsyncMock(side_effect=mock_refresh)
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    f"/api/v1/analyses/{analysis_id}/feedback",
                    json={"is_helpful": True, "comment": "Very helpful!"},
                )
                assert response.status_code == 201
                mock_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_feedback_returns_created_record(self):
        """Feedback endpoint should return the created feedback."""
        from unittest.mock import patch

        from fastapi import FastAPI

        from heisenberg.backend.models import Analysis
        from heisenberg.backend.routers import feedback as feedback_router

        app = FastAPI()
        app.include_router(feedback_router.router, prefix="/api/v1")

        analysis_id = uuid.uuid4()
        feedback_id = uuid.uuid4()
        mock_analysis = MagicMock(spec=Analysis)
        mock_analysis.id = analysis_id

        with patch.object(feedback_router, "get_db_session") as mock_get_db:
            mock_session = AsyncMock()
            mock_session.get = AsyncMock(return_value=mock_analysis)

            def capture_feedback(fb):
                fb.id = feedback_id
                fb.created_at = datetime.now(UTC)

            mock_session.add = MagicMock(side_effect=capture_feedback)
            mock_session.commit = AsyncMock()
            mock_session.refresh = AsyncMock()
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    f"/api/v1/analyses/{analysis_id}/feedback",
                    json={"is_helpful": False, "comment": "Wrong diagnosis"},
                )
                assert response.status_code == 201
                data = response.json()
                assert not data["is_helpful"]
                assert data["comment"] == "Wrong diagnosis"
                assert "id" in data
                assert "created_at" in data


class TestFeedbackStats:
    """Test suite for feedback statistics."""

    def test_feedback_stats_schema_exists(self):
        """FeedbackStats schema should be importable."""
        from heisenberg.backend.schemas import FeedbackStats

        assert FeedbackStats is not None

    def test_feedback_stats_has_fields(self):
        """FeedbackStats should have expected fields."""
        from heisenberg.backend.schemas import FeedbackStats

        stats = FeedbackStats(
            total_feedback=100,
            helpful_count=80,
            not_helpful_count=20,
            helpful_percentage=80.0,
        )
        assert stats.total_feedback == 100
        assert stats.helpful_percentage == pytest.approx(80.0)

    @pytest.mark.asyncio
    async def test_feedback_stats_endpoint_exists(self):
        """GET /api/v1/feedback/stats should exist."""
        from unittest.mock import patch

        from fastapi import FastAPI

        from heisenberg.backend.routers import feedback

        app = FastAPI()
        app.include_router(feedback.router, prefix="/api/v1")

        # Mock the database session for stats query
        with patch.object(feedback, "get_db_session") as mock_get_db:
            mock_result = MagicMock()
            mock_result.scalar.return_value = 0

            mock_session = AsyncMock()
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/v1/feedback/stats")
                assert response.status_code == 200
                data = response.json()
                assert "total_feedback" in data
                assert "helpful_count" in data


class TestAnalysisFeedbackRelation:
    """Test suite for Analysis-Feedback relationship."""

    def test_analysis_has_feedback_relation(self):
        """Analysis model should have feedbacks relationship."""
        from heisenberg.backend.models import Analysis

        assert hasattr(Analysis, "feedbacks")

    def test_feedback_cascades_on_analysis_delete(self):
        """Feedback should be deleted when Analysis is deleted."""
        from heisenberg.backend.models import Analysis

        # Check cascade setting in relationship
        feedbacks_rel = Analysis.__mapper__.relationships.get("feedbacks")
        assert feedbacks_rel is not None
        assert "delete-orphan" in feedbacks_rel.cascade


class TestFeedbackMigration:
    """Test suite for feedback migration."""

    def test_feedback_migration_exists(self):
        """Feedback migration file should exist."""
        from pathlib import Path

        migrations_dir = Path("migrations/versions")
        migration_files = list(migrations_dir.glob("*feedback*.py"))
        assert len(migration_files) >= 1, "Feedback migration not found"

    def test_feedback_migration_has_upgrade(self):
        """Feedback migration should have upgrade function."""
        import importlib.util
        from pathlib import Path

        migrations_dir = Path("migrations/versions")
        migration_files = list(migrations_dir.glob("*feedback*.py"))
        assert len(migration_files) >= 1

        # Load the migration module
        spec = importlib.util.spec_from_file_location("feedback_migration", migration_files[0])
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert hasattr(module, "upgrade")
        assert callable(module.upgrade)

    def test_feedback_migration_has_downgrade(self):
        """Feedback migration should have downgrade function."""
        import importlib.util
        from pathlib import Path

        migrations_dir = Path("migrations/versions")
        migration_files = list(migrations_dir.glob("*feedback*.py"))
        assert len(migration_files) >= 1

        spec = importlib.util.spec_from_file_location("feedback_migration", migration_files[0])
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert hasattr(module, "downgrade")
        assert callable(module.downgrade)
