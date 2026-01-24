"""LLM router with fallback support."""

from __future__ import annotations

from typing import Any

from heisenberg.backend.llm.base import LLMProvider
from heisenberg.backend.logging import get_logger

logger = get_logger(__name__)


class LLMRouter:
    """Routes LLM requests with automatic fallback on failure."""

    def __init__(self, providers: list[LLMProvider]) -> None:
        """
        Initialize the router with ordered providers.

        Args:
            providers: List of providers in priority order (first is primary).
        """
        if not providers:
            raise ValueError("At least one provider is required")

        self._providers = providers

    @property
    def providers(self) -> list[LLMProvider]:
        """Return the list of providers."""
        return self._providers

    async def analyze(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Analyze using providers with automatic fallback.

        Args:
            system_prompt: System prompt for the LLM.
            user_prompt: User prompt containing test failure details.
            **kwargs: Additional arguments passed to providers.

        Returns:
            Dictionary with response, input_tokens, output_tokens, provider.

        Raises:
            Exception: If all providers fail.
        """
        last_error: Exception | None = None

        for provider in self._providers:
            try:
                logger.info(
                    "llm_router_attempt",
                    provider=provider.name,
                )

                result = await provider.analyze(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    **kwargs,
                )

                # Add provider info to result
                result["provider"] = provider.name

                logger.info(
                    "llm_router_success",
                    provider=provider.name,
                    input_tokens=result.get("input_tokens"),
                    output_tokens=result.get("output_tokens"),
                )

                return result

            except Exception as e:
                last_error = e
                logger.warning(
                    "llm_router_fallback",
                    failed_provider=provider.name,
                    error=str(e),
                )
                continue

        # All providers failed
        logger.error(
            "llm_router_all_failed",
            providers=[p.name for p in self._providers],
            last_error=str(last_error),
        )

        if last_error:
            raise last_error
        raise RuntimeError("All LLM providers failed")
