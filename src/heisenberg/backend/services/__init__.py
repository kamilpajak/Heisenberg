"""Backend services for Heisenberg."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from uuid import UUID

from heisenberg.backend.cost_tracking import CostCalculator
from heisenberg.backend.llm import create_provider
from heisenberg.backend.llm.router import LLMRouter
from heisenberg.backend.models import UsageRecord

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def create_llm_service(
    primary_provider: str,
    fallback_provider: str | None = None,
    anthropic_api_key: str | None = None,
    openai_api_key: str | None = None,
) -> LLMRouter:
    """
    Create an LLM service with optional fallback.

    Args:
        primary_provider: Name of the primary provider ('claude' or 'openai').
        fallback_provider: Optional name of the fallback provider.
        anthropic_api_key: Anthropic API key (or from env).
        openai_api_key: OpenAI API key (or from env).

    Returns:
        Configured LLMRouter with providers.

    Raises:
        ValueError: If required API key is missing.
    """
    providers = []

    # Get API keys from environment if not provided
    anthropic_key = anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
    openai_key = openai_api_key or os.environ.get("OPENAI_API_KEY")

    # Create primary provider
    if primary_provider == "claude":
        if not anthropic_key:
            raise ValueError("Anthropic API key required for Claude provider")
        providers.append(create_provider("claude", api_key=anthropic_key))
    elif primary_provider == "openai":
        if not openai_key:
            raise ValueError("OpenAI API key required for OpenAI provider")
        providers.append(create_provider("openai", api_key=openai_key))
    else:
        raise ValueError(f"Unknown provider: {primary_provider}")

    # Create fallback provider if specified
    if fallback_provider:
        if fallback_provider == "claude":
            if not anthropic_key:
                raise ValueError("Anthropic API key required for Claude fallback")
            providers.append(create_provider("claude", api_key=anthropic_key))
        elif fallback_provider == "openai":
            if not openai_key:
                raise ValueError("OpenAI API key required for OpenAI fallback")
            providers.append(create_provider("openai", api_key=openai_key))
        else:
            raise ValueError(f"Unknown fallback provider: {fallback_provider}")

    return LLMRouter(providers=providers)


async def record_usage(
    session: AsyncSession,
    organization_id: UUID,
    analysis_id: UUID,
    model_name: str,
    input_tokens: int,
    output_tokens: int,
) -> UsageRecord:
    """
    Record LLM usage and calculate cost.

    Args:
        session: Database session.
        organization_id: Organization ID.
        analysis_id: Analysis ID.
        model_name: Name of the LLM model used.
        input_tokens: Number of input tokens.
        output_tokens: Number of output tokens.

    Returns:
        Created UsageRecord with calculated cost.
    """
    calculator = CostCalculator()
    cost = calculator.calculate_cost(model_name, input_tokens, output_tokens)

    record = UsageRecord(
        organization_id=organization_id,
        analysis_id=analysis_id,
        model_name=model_name,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost,
    )

    session.add(record)
    await session.commit()
    await session.refresh(record)

    return record
