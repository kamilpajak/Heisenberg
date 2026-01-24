"""Tests for async task queue - TDD for Phase 6."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestTaskModel:
    """Test suite for AsyncTask model."""

    def test_async_task_model_exists(self):
        """AsyncTask model should be importable."""
        from heisenberg.backend.models import AsyncTask

        assert AsyncTask is not None

    def test_async_task_has_required_fields(self):
        """AsyncTask model should have required fields."""
        from heisenberg.backend.models import AsyncTask

        columns = {c.name for c in AsyncTask.__table__.columns}
        assert "id" in columns
        assert "organization_id" in columns
        assert "task_type" in columns
        assert "status" in columns
        assert "payload" in columns
        assert "result" in columns
        assert "error_message" in columns
        assert "created_at" in columns
        assert "started_at" in columns
        assert "completed_at" in columns

    def test_async_task_status_values(self):
        """AsyncTask should support expected status values."""
        from heisenberg.backend.models import TaskStatus

        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"


class TestTaskQueue:
    """Test suite for TaskQueue service."""

    def test_task_queue_exists(self):
        """TaskQueue should be importable."""
        from heisenberg.backend.task_queue import TaskQueue

        assert TaskQueue is not None

    @pytest.mark.asyncio
    async def test_enqueue_creates_task(self):
        """enqueue should create a pending task."""
        from heisenberg.backend.task_queue import TaskQueue

        queue = TaskQueue()
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        task = await queue.enqueue(
            session=mock_session,
            organization_id=uuid.uuid4(),
            task_type="analyze",
            payload={"test": "data"},
        )

        mock_session.add.assert_called_once()
        assert task is not None

    @pytest.mark.asyncio
    async def test_get_task_by_id(self):
        """Should be able to retrieve task by ID."""
        from heisenberg.backend.models import AsyncTask, TaskStatus
        from heisenberg.backend.task_queue import TaskQueue

        queue = TaskQueue()
        task_id = uuid.uuid4()

        mock_task = MagicMock(spec=AsyncTask)
        mock_task.id = task_id
        mock_task.status = TaskStatus.PENDING

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_task)

        result = await queue.get_task(session=mock_session, task_id=task_id)

        assert result is not None
        assert result.id == task_id

    @pytest.mark.asyncio
    async def test_update_task_status(self):
        """Should be able to update task status."""
        from heisenberg.backend.models import AsyncTask, TaskStatus
        from heisenberg.backend.task_queue import TaskQueue

        queue = TaskQueue()
        task_id = uuid.uuid4()

        mock_task = MagicMock(spec=AsyncTask)
        mock_task.id = task_id
        mock_task.status = TaskStatus.PENDING

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_task)
        mock_session.commit = AsyncMock()

        await queue.update_status(
            session=mock_session,
            task_id=task_id,
            status=TaskStatus.RUNNING,
        )

        assert mock_task.status == TaskStatus.RUNNING


class TestTaskSchemas:
    """Test suite for task queue schemas."""

    def test_task_create_schema_exists(self):
        """TaskCreate schema should be importable."""
        from heisenberg.backend.schemas import TaskCreate

        assert TaskCreate is not None

    def test_task_response_schema_exists(self):
        """TaskResponse schema should be importable."""
        from heisenberg.backend.schemas import TaskResponse

        assert TaskResponse is not None

    def test_task_response_has_fields(self):
        """TaskResponse should have expected fields."""
        from heisenberg.backend.schemas import TaskResponse

        response = TaskResponse(
            id=uuid.uuid4(),
            task_type="analyze",
            status="pending",
            created_at=datetime.now(UTC),
            started_at=None,
            completed_at=None,
        )
        assert response.status == "pending"


class TestTaskEndpoints:
    """Test suite for task queue API endpoints."""

    @pytest.mark.asyncio
    async def test_create_task_endpoint_exists(self):
        """POST /api/v1/tasks should exist."""
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        from heisenberg.backend.routers import tasks

        app = FastAPI()
        app.include_router(tasks.router, prefix="/api/v1")

        with patch.object(tasks, "get_db_session") as mock_get_db:
            mock_session = AsyncMock()
            mock_session.add = MagicMock()
            mock_session.commit = AsyncMock()

            async def mock_refresh(task):
                task.id = uuid.uuid4()
                task.created_at = datetime.now(UTC)
                task.status = "pending"

            mock_session.refresh = AsyncMock(side_effect=mock_refresh)
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/tasks",
                    json={
                        "organization_id": str(uuid.uuid4()),
                        "task_type": "analyze",
                        "payload": {"test": "data"},
                    },
                )
                assert response.status_code != 404

    @pytest.mark.asyncio
    async def test_get_task_endpoint_exists(self):
        """GET /api/v1/tasks/{id} should exist."""
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        from heisenberg.backend.models import AsyncTask
        from heisenberg.backend.routers import tasks

        app = FastAPI()
        app.include_router(tasks.router, prefix="/api/v1")

        task_id = uuid.uuid4()
        mock_task = MagicMock(spec=AsyncTask)
        mock_task.id = task_id
        mock_task.task_type = "analyze"
        mock_task.status = "pending"
        mock_task.payload = {}
        mock_task.result = None
        mock_task.error_message = None
        mock_task.created_at = datetime.now(UTC)
        mock_task.started_at = None
        mock_task.completed_at = None

        with patch.object(tasks, "get_db_session") as mock_get_db:
            mock_session = AsyncMock()
            mock_session.get = AsyncMock(return_value=mock_task)
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(f"/api/v1/tasks/{task_id}")
                assert response.status_code == 200


class TestWebhookCallback:
    """Test suite for webhook callbacks."""

    def test_webhook_config_in_settings(self):
        """Settings should have webhook configuration."""
        from heisenberg.backend.config import Settings

        settings = Settings(
            database_url="postgresql://test:test@localhost/test",
            secret_key="test-secret-key",
        )
        assert hasattr(settings, "webhook_url")
        assert settings.webhook_url is None  # default

    def test_send_webhook_function_exists(self):
        """send_webhook function should exist."""
        from heisenberg.backend.task_queue import send_webhook

        assert send_webhook is not None

    @pytest.mark.asyncio
    async def test_send_webhook_posts_to_url(self):
        """send_webhook should POST task result to webhook URL."""
        from heisenberg.backend.task_queue import send_webhook

        with patch("heisenberg.backend.task_queue.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__ = AsyncMock(
                return_value=MagicMock(post=AsyncMock(return_value=mock_response))
            )
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await send_webhook(
                url="https://example.com/webhook",
                task_id=uuid.uuid4(),
                status="completed",
                result={"analysis": "done"},
            )

            assert result is True


class TestTaskMigration:
    """Test suite for task queue migration."""

    def test_task_migration_exists(self):
        """Task queue migration file should exist."""
        from pathlib import Path

        migrations_dir = Path("migrations/versions")
        migration_files = list(migrations_dir.glob("*task*.py"))
        assert len(migration_files) >= 1, "Task queue migration not found"
