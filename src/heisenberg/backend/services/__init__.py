"""Backend services for Heisenberg."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from uuid import UUID

from heisenberg.backend.cost_tracking import CostCalculator
from heisenberg.backend.models import UsageRecord
from heisenberg.llm.providers import create_provider
from heisenberg.llm.router import LLMRouter

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _get_api_keys(
    anthropic_api_key: str | None = None,
    openai_api_key: str | None = None,
    google_api_key: str | None = None,
) -> dict[str, str | None]:
    """Get API keys from arguments or environment."""
    return {
        "anthropic": anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY"),
        "openai": openai_api_key or os.environ.get("OPENAI_API_KEY"),
        "google": google_api_key or os.environ.get("GOOGLE_API_KEY"),
    }


def _create_single_provider(provider_name: str, api_keys: dict[str, str | None]):
    """Create a single LLM provider.

    Raises:
        ValueError: If provider is unknown or API key is missing.
    """
    if provider_name not in api_keys:
        raise ValueError(f"Unknown provider: {provider_name}")

    api_key = api_keys[provider_name]
    if not api_key:
        raise ValueError(f"API key required for {provider_name} provider")

    return create_provider(provider_name, api_key=api_key)


def create_llm_service(
    primary_provider: str,
    fallback_provider: str | None = None,
    anthropic_api_key: str | None = None,
    openai_api_key: str | None = None,
    google_api_key: str | None = None,
) -> LLMRouter:
    """
    Create an LLM service with optional fallback.

    Args:
        primary_provider: Name of the primary provider ('anthropic', 'openai', or 'google').
        fallback_provider: Optional name of the fallback provider.
        anthropic_api_key: Anthropic API key (or from env).
        openai_api_key: OpenAI API key (or from env).
        google_api_key: Google API key (or from env).

    Returns:
        Configured LLMRouter with providers.

    Raises:
        ValueError: If required API key is missing.
    """
    api_keys = _get_api_keys(anthropic_api_key, openai_api_key, google_api_key)

    providers = [_create_single_provider(primary_provider, api_keys)]

    if fallback_provider:
        providers.append(_create_single_provider(fallback_provider, api_keys))

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
