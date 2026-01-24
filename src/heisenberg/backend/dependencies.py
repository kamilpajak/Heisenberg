"""FastAPI dependency injection for Heisenberg backend."""

from __future__ import annotations

from functools import lru_cache

from heisenberg.backend.config import get_settings
from heisenberg.backend.llm.adapter import LLMRouterAdapter
from heisenberg.backend.llm.router import LLMRouter
from heisenberg.backend.services import create_llm_service
from heisenberg.backend.services.analyze import AnalyzeService


@lru_cache
def get_llm_service() -> LLMRouter:
    """
    Get configured LLM service.

    Returns:
        LLMRouter with configured providers.
    """
    settings = get_settings()

    return create_llm_service(
        primary_provider=settings.llm_primary_provider,
        fallback_provider=settings.llm_fallback_provider,
        anthropic_api_key=settings.anthropic_api_key,
        openai_api_key=settings.openai_api_key,
    )


def get_analyze_service() -> AnalyzeService:
    """
    Get configured analyze service.

    Returns:
        AnalyzeService with LLM router adapter.
    """
    llm_router = get_llm_service()
    adapter = LLMRouterAdapter(llm_router)
    return AnalyzeService(llm_client=adapter)
