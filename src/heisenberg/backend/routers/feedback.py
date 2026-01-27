"""API router for feedback endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from heisenberg.backend.database import get_db
from heisenberg.backend.logging import get_logger
from heisenberg.backend.models import Analysis, Feedback
from heisenberg.backend.schemas import FeedbackCreate, FeedbackResponse, FeedbackStats

logger = get_logger(__name__)

router = APIRouter(tags=["Feedback"])

# Type alias for dependency injection
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.post(
    "/analyses/{analysis_id}/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit feedback on an analysis",
    description="Submit user feedback (helpful/not helpful) on an AI analysis.",
)
async def create_feedback(
    analysis_id: UUID,
    feedback_data: FeedbackCreate,
    session: DbSession,
) -> FeedbackResponse:
    """
    Create feedback for an analysis.

    Args:
        analysis_id: UUID of the analysis to provide feedback on.
        feedback_data: Feedback data (is_helpful, optional comment).
        session: Database session (injected).

    Returns:
        Created feedback record.

    Raises:
        HTTPException: 404 if analysis not found.
    """
    # Check if analysis exists
    analysis = await session.get(Analysis, analysis_id)
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis {analysis_id} not found",
        )

    # Create feedback
    feedback = Feedback(
        analysis_id=analysis_id,
        is_helpful=feedback_data.is_helpful,
        comment=feedback_data.comment,
    )
    session.add(feedback)
    await session.commit()
    await session.refresh(feedback)

    logger.info(
        "feedback_created",
        feedback_id=str(feedback.id),
        analysis_id=str(analysis_id),
        is_helpful=feedback_data.is_helpful,
    )

    return FeedbackResponse(
        id=feedback.id,
        analysis_id=feedback.analysis_id,
        is_helpful=feedback.is_helpful,
        comment=feedback.comment,
        created_at=feedback.created_at,
    )


@router.get(
    "/feedback/stats",
    response_model=FeedbackStats,
    summary="Get feedback statistics",
    description="Get aggregated statistics on all feedback.",
)
async def get_feedback_stats(session: DbSession) -> FeedbackStats:
    """
    Get aggregated feedback statistics.

    Args:
        session: Database session (injected).

    Returns:
        Feedback statistics including totals and percentages.
    """
    # Get counts
    total_result = await session.execute(select(func.count(Feedback.id)))
    total = total_result.scalar() or 0

    helpful_result = await session.execute(
        select(func.count(Feedback.id)).where(Feedback.is_helpful.is_(True))
    )
    helpful = helpful_result.scalar() or 0

    not_helpful = total - helpful
    percentage = (helpful / total * 100) if total > 0 else 0.0

    return FeedbackStats(
        total_feedback=total,
        helpful_count=helpful,
        not_helpful_count=not_helpful,
        helpful_percentage=round(percentage, 1),
    )
