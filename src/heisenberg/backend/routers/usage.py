"""API router for usage tracking endpoints."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from heisenberg.backend.logging import get_logger
from heisenberg.backend.models import UsageRecord
from heisenberg.backend.schemas import UsageSummary

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.ext.asyncio import AsyncSession

# Query parameter annotations
OrgIdQuery = Annotated[UUID, Query(description="Organization ID")]
DaysQuery = Annotated[int, Query(ge=1, le=365, description="Number of days to include")]

logger = get_logger(__name__)

router = APIRouter(prefix="/usage", tags=["Usage"])


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


@router.get(
    "/summary",
    response_model=UsageSummary,
    summary="Get usage summary",
    description="Get aggregated usage statistics for an organization.",
)
async def get_usage_summary(
    organization_id: OrgIdQuery,
    days: DaysQuery = 30,
) -> UsageSummary:
    """
    Get usage summary for an organization.

    Args:
        organization_id: UUID of the organization.
        days: Number of days to look back.

    Returns:
        Aggregated usage statistics.
    """
    period_end = datetime.now(UTC)
    period_start = period_end - timedelta(days=days)

    async with get_db_session() as session:
        # Get aggregated stats
        result = await session.execute(
            select(
                func.count(UsageRecord.id).label("total_requests"),
                func.coalesce(func.sum(UsageRecord.input_tokens), 0).label(
                    "total_input_tokens"
                ),
                func.coalesce(func.sum(UsageRecord.output_tokens), 0).label(
                    "total_output_tokens"
                ),
                func.coalesce(func.sum(UsageRecord.cost_usd), Decimal("0")).label(
                    "total_cost_usd"
                ),
            ).where(
                UsageRecord.organization_id == organization_id,
                UsageRecord.created_at >= period_start,
                UsageRecord.created_at <= period_end,
            )
        )
        row = result.one()

        # Get breakdown by model
        model_result = await session.execute(
            select(
                UsageRecord.model_name,
                func.count(UsageRecord.id).label("requests"),
                func.sum(UsageRecord.cost_usd).label("cost_usd"),
            )
            .where(
                UsageRecord.organization_id == organization_id,
                UsageRecord.created_at >= period_start,
                UsageRecord.created_at <= period_end,
            )
            .group_by(UsageRecord.model_name)
        )
        by_model = {
            row.model_name: {
                "requests": row.requests,
                "cost_usd": str(row.cost_usd or Decimal("0")),
            }
            for row in model_result.all()
        }

        return UsageSummary(
            organization_id=organization_id,
            period_start=period_start,
            period_end=period_end,
            total_requests=row.total_requests or 0,
            total_input_tokens=row.total_input_tokens or 0,
            total_output_tokens=row.total_output_tokens or 0,
            total_cost_usd=row.total_cost_usd or Decimal("0"),
            by_model=by_model,
        )


@router.get(
    "/by-model",
    summary="Get usage breakdown by model",
    description="Get usage statistics grouped by LLM model.",
)
async def get_usage_by_model(
    organization_id: OrgIdQuery,
    days: DaysQuery = 30,
) -> list[dict]:
    """
    Get usage breakdown by model.

    Args:
        organization_id: UUID of the organization.
        days: Number of days to look back.

    Returns:
        List of usage records grouped by model.
    """
    period_start = datetime.now(UTC) - timedelta(days=days)

    async with get_db_session() as session:
        result = await session.execute(
            select(
                UsageRecord.model_name,
                func.count(UsageRecord.id).label("requests"),
                func.sum(UsageRecord.input_tokens).label("input_tokens"),
                func.sum(UsageRecord.output_tokens).label("output_tokens"),
                func.sum(UsageRecord.cost_usd).label("cost_usd"),
            )
            .where(
                UsageRecord.organization_id == organization_id,
                UsageRecord.created_at >= period_start,
            )
            .group_by(UsageRecord.model_name)
            .order_by(func.sum(UsageRecord.cost_usd).desc())
        )

        return [
            {
                "model_name": row.model_name,
                "requests": row.requests,
                "input_tokens": row.input_tokens or 0,
                "output_tokens": row.output_tokens or 0,
                "cost_usd": str(row.cost_usd or Decimal("0")),
            }
            for row in result.all()
        ]
