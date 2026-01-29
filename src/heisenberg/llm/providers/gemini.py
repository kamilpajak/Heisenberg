"""Google Gemini LLM provider with dual-mode support."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from heisenberg.llm.config import PROVIDER_CONFIGS
from heisenberg.llm.models import LLMAnalysis

if TYPE_CHECKING:
    from google.genai import Client

logger = logging.getLogger(__name__)


class GeminiProvider:
    """LLM provider for Google's Gemini models with sync + async support."""

    def __init__(
        self,
        api_key: str,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> None:
        """
        Initialize Gemini provider.

        Args:
            api_key: Google API key.
            model: Model name to use. Defaults to config default.
            max_tokens: Maximum tokens in response. Defaults to config default.
            temperature: Temperature for sampling. Defaults to config default.
        """
        config = PROVIDER_CONFIGS["google"]
        self._api_key = api_key
        self._model = model or config.default_model
        self._max_tokens = max_tokens if max_tokens is not None else config.max_tokens
        self._temperature = temperature if temperature is not None else config.temperature
        self._client: Client | None = None

    @property
    def name(self) -> str:
        """Return the provider name."""
        return "google"

    @property
    def model(self) -> str:
        """Return the model name."""
        return self._model

    def is_available(self) -> bool:
        """Check if the provider is available."""
        return bool(self._api_key)

    def _get_client(self) -> Client:
        """Get or create Gemini client (used for both sync and async)."""
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self._api_key)
        return self._client

    def _get_config(self, system_prompt: str | None) -> Any:
        """Create generate content config."""
        from google.genai import types

        return types.GenerateContentConfig(
            system_instruction=system_prompt or "",
            max_output_tokens=self._max_tokens,
            temperature=self._temperature,
        )

    def _extract_token_counts(self, response: Any) -> tuple[int, int]:
        """Extract token counts from response metadata."""
        input_tokens = 0
        output_tokens = 0
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
            output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0
        return input_tokens, output_tokens

    def analyze(
        self,
        user_prompt: str,
        *,
        system_prompt: str | None = None,
    ) -> LLMAnalysis:
        """
        Analyze using Gemini (synchronous).

        Args:
            user_prompt: User prompt containing the analysis request.
            system_prompt: Optional system prompt for context.

        Returns:
            LLMAnalysis with response content and token usage.
        """
        client = self._get_client()
        config = self._get_config(system_prompt)

        logger.debug(
            "gemini_analyze_request: model=%s, max_tokens=%d",
            self._model,
            self._max_tokens,
        )

        response = client.models.generate_content(
            model=self._model,
            contents=user_prompt,
            config=config,
        )

        input_tokens, output_tokens = self._extract_token_counts(response)

        result = LLMAnalysis(
            content=response.text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=self._model,
            provider=self.name,
        )

        logger.debug(
            "gemini_analyze_response: input_tokens=%d, output_tokens=%d",
            result.input_tokens,
            result.output_tokens,
        )

        return result

    async def analyze_async(
        self,
        user_prompt: str,
        *,
        system_prompt: str | None = None,
    ) -> LLMAnalysis:
        """
        Analyze using Gemini (asynchronous).

        Args:
            user_prompt: User prompt containing the analysis request.
            system_prompt: Optional system prompt for context.

        Returns:
            LLMAnalysis with response content and token usage.
        """
        client = self._get_client()
        config = self._get_config(system_prompt)

        logger.debug(
            "gemini_analyze_async_request: model=%s, max_tokens=%d",
            self._model,
            self._max_tokens,
        )

        response = await client.aio.models.generate_content(
            model=self._model,
            contents=user_prompt,
            config=config,
        )

        input_tokens, output_tokens = self._extract_token_counts(response)

        result = LLMAnalysis(
            content=response.text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=self._model,
            provider=self.name,
        )

        logger.debug(
            "gemini_analyze_async_response: input_tokens=%d, output_tokens=%d",
            result.input_tokens,
            result.output_tokens,
        )

        return result

    def analyze_with_image(
        self,
        user_prompt: str,
        image_data: bytes,
        mime_type: str = "image/png",
        *,
        system_prompt: str | None = None,
    ) -> LLMAnalysis:
        """
        Analyze with an image using Gemini's vision capability (synchronous).

        This is a Gemini-specific method not part of the LLMProvider protocol,
        as not all providers support vision.

        Args:
            user_prompt: User prompt describing what to analyze.
            image_data: Raw image bytes.
            mime_type: Image MIME type (default: image/png).
            system_prompt: Optional system prompt for context.

        Returns:
            LLMAnalysis with response content and token usage.
        """
        from google.genai import types

        client = self._get_client()
        config = self._get_config(system_prompt)

        # Build multimodal content: text prompt + image
        image_part = types.Part.from_bytes(data=image_data, mime_type=mime_type)
        contents = [user_prompt, image_part]

        logger.debug(
            "gemini_vision_request: model=%s, mime_type=%s, image_size=%d",
            self._model,
            mime_type,
            len(image_data),
        )

        response = client.models.generate_content(
            model=self._model,
            contents=contents,
            config=config,
        )

        input_tokens, output_tokens = self._extract_token_counts(response)

        result = LLMAnalysis(
            content=response.text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=self._model,
            provider=self.name,
        )

        logger.debug(
            "gemini_vision_response: input_tokens=%d, output_tokens=%d",
            result.input_tokens,
            result.output_tokens,
        )

        return result

    async def _call_api(
        self,
        user_prompt: str,
        *,
        system_prompt: str | None = None,
    ) -> LLMAnalysis:
        """Internal API call method for mocking in tests."""
        return await self.analyze_async(user_prompt, system_prompt=system_prompt)
