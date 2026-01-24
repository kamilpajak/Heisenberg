"""API router for async task endpoints."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from heisenberg.backend.logging import get_logger
from heisenberg.backend.models import AsyncTask
from heisenberg.backend.schemas import TaskCreate, TaskResponse
from heisenberg.backend.task_queue import TaskQueue

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

router = APIRouter(prefix="/tasks", tags=["Tasks"])

# Task queue instance
task_queue = TaskQueue()


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session."""
    from heisenberg.backend.database import _session_maker

    if _session_maker is None:
        raise RuntimeError("Database not initialized")

    async with _session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an async task",
    description="Create a new async task for background processing.",
)
async def create_task(task_data: TaskCreate) -> TaskResponse:
    """
    Create a new async task.

    Args:
        task_data: Task creation data.

    Returns:
        Created task.
    """
    async with get_db_session() as session:
        task = await task_queue.enqueue(
            session=session,
            organization_id=task_data.organization_id,
            task_type=task_data.task_type,
            payload=task_data.payload,
        )

        # Handle both enum and string status values
        status_value = task.status.value if hasattr(task.status, "value") else task.status

        return TaskResponse(
            id=task.id,
            task_type=task.task_type,
            status=status_value,
            payload=task.payload,
            result=task.result,
            error_message=task.error_message,
            created_at=task.created_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
        )


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Get task by ID",
    description="Get the status and details of an async task.",
)
async def get_task(task_id: UUID) -> TaskResponse:
    """
    Get a task by ID.

    Args:
        task_id: Task UUID.

    Returns:
        Task details.

    Raises:
        HTTPException: 404 if task not found.
    """
    async with get_db_session() as session:
        task = await session.get(AsyncTask, task_id)

        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task {task_id} not found",
            )

        # Handle both enum and string status values
        status_value = task.status.value if hasattr(task.status, "value") else task.status

        return TaskResponse(
            id=task.id,
            task_type=task.task_type,
            status=status_value,
            payload=task.payload,
            result=task.result,
            error_message=task.error_message,
            created_at=task.created_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
        )
