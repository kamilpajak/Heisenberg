"""Google Gemini LLM provider."""

from __future__ import annotations

from typing import Any

from google import genai
from google.genai import types

from heisenberg.backend.llm.base import LLMProvider
from heisenberg.backend.logging import get_logger
from heisenberg.llm.models import LLMAnalysis

logger = get_logger(__name__)


class GeminiProvider(LLMProvider):
    """LLM provider for Google's Gemini models."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-3-pro-preview",
        max_tokens: int = 4096,
    ) -> None:
        """
        Initialize Gemini provider.

        Args:
            api_key: Google API key.
            model: Model name to use.
            max_tokens: Maximum tokens in response.
        """
        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens
        self._client = genai.Client(api_key=api_key)

    @property
    def name(self) -> str:
        """Return the provider name."""
        return "gemini"

    @property
    def model(self) -> str:
        """Return the model name."""
        return self._model

    def is_available(self) -> bool:
        """Check if the provider is available."""
        return bool(self._api_key)

    async def analyze(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs: Any,
    ) -> LLMAnalysis:
        """
        Analyze test failure using Gemini.

        Args:
            system_prompt: System prompt for Gemini.
            user_prompt: User prompt containing test failure details.
            **kwargs: Additional arguments (model, max_tokens).

        Returns:
            LLMAnalysis with response content and token usage.
        """
        model_name = kwargs.get("model", self._model)
        max_tokens = kwargs.get("max_tokens", self._max_tokens)

        logger.debug(
            "gemini_analyze_request",
            model=model_name,
            max_tokens=max_tokens,
        )

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=max_tokens,
        )

        response = await self._client.aio.models.generate_content(
            model=model_name,
            contents=user_prompt,
            config=config,
        )

        # Extract token counts from usage metadata
        input_tokens = 0
        output_tokens = 0
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
            output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

        result = LLMAnalysis(
            content=response.text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=model_name,
            provider=self.name,
        )

        logger.debug(
            "gemini_analyze_response",
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        )

        return result

    async def _call_api(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs: Any,
    ) -> LLMAnalysis:
        """Internal API call method for mocking in tests."""
        return await self.analyze(system_prompt, user_prompt, **kwargs)
