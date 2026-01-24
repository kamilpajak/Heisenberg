"""Async task queue for background processing."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

import httpx

from heisenberg.backend.logging import get_logger
from heisenberg.backend.models import AsyncTask, TaskStatus

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


class TaskQueue:
    """Service for managing async tasks."""

    async def enqueue(
        self,
        session: AsyncSession,
        organization_id: UUID,
        task_type: str,
        payload: dict[str, Any] | None = None,
    ) -> AsyncTask:
        """
        Create a new pending task.

        Args:
            session: Database session.
            organization_id: Organization ID.
            task_type: Type of task (e.g., "analyze").
            payload: Task payload data.

        Returns:
            Created AsyncTask.
        """
        task = AsyncTask(
            organization_id=organization_id,
            task_type=task_type,
            status=TaskStatus.PENDING,
            payload=payload or {},
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)

        logger.info(
            "task_enqueued",
            task_id=str(task.id),
            task_type=task_type,
            organization_id=str(organization_id),
        )

        return task

    async def get_task(
        self,
        session: AsyncSession,
        task_id: UUID,
    ) -> AsyncTask | None:
        """
        Get a task by ID.

        Args:
            session: Database session.
            task_id: Task ID.

        Returns:
            AsyncTask or None if not found.
        """
        return await session.get(AsyncTask, task_id)

    async def update_status(
        self,
        session: AsyncSession,
        task_id: UUID,
        status: TaskStatus,
        result: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> AsyncTask | None:
        """
        Update task status.

        Args:
            session: Database session.
            task_id: Task ID.
            status: New status.
            result: Optional result data.
            error_message: Optional error message.

        Returns:
            Updated AsyncTask or None if not found.
        """
        task = await session.get(AsyncTask, task_id)
        if task is None:
            return None

        task.status = status

        if status == TaskStatus.RUNNING:
            task.started_at = datetime.now(UTC)
        elif status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            task.completed_at = datetime.now(UTC)

        if result is not None:
            task.result = result
        if error_message is not None:
            task.error_message = error_message

        await session.commit()

        logger.info(
            "task_status_updated",
            task_id=str(task_id),
            status=status.value,
        )

        return task


async def send_webhook(
    url: str,
    task_id: UUID,
    status: str,
    result: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> bool:
    """
    Send webhook notification for task completion.

    Args:
        url: Webhook URL to POST to.
        task_id: Task ID.
        status: Task status.
        result: Optional task result.
        error_message: Optional error message.

    Returns:
        True if webhook was sent successfully.
    """
    payload = {
        "task_id": str(task_id),
        "status": status,
        "result": result,
        "error_message": error_message,
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                timeout=30.0,
            )
            success = response.status_code < 400

            logger.info(
                "webhook_sent",
                url=url,
                task_id=str(task_id),
                status_code=response.status_code,
                success=success,
            )

            return success

    except Exception as e:
        logger.error(
            "webhook_failed",
            url=url,
            task_id=str(task_id),
            error=str(e),
        )
        return False
