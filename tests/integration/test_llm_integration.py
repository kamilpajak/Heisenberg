"""Integration tests for real LLM API calls.

These tests require actual API keys and make real API calls.
They are skipped by default unless API keys are set.

Run with: pytest tests/test_llm_integration.py -v --run-integration
"""

import os

import pytest

# Skip all tests in this module if --run-integration not provided
pytestmark = pytest.mark.integration


def has_anthropic_key() -> bool:
    """Check if Anthropic API key is available."""
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def has_openai_key() -> bool:
    """Check if OpenAI API key is available."""
    return bool(os.environ.get("OPENAI_API_KEY"))


def has_google_key() -> bool:
    """Check if Google API key is available."""
    return bool(os.environ.get("GOOGLE_API_KEY"))


# Sample test data
SAMPLE_FAILED_TEST = {
    "name": "test_login_flow",
    "file": "tests/auth.spec.ts",
    "error_message": "Timeout waiting for selector '#login-button'",
    "stack_trace": "at tests/auth.spec.ts:15:10",
    "duration_ms": 30000,
    "retry_count": 2,
}


class TestAnthropicIntegration:
    """Integration tests for Anthropic/Claude API."""

    @pytest.mark.skipif(not has_anthropic_key(), reason="ANTHROPIC_API_KEY not set")
    @pytest.mark.asyncio
    async def test_claude_provider_initializes(self):
        """Claude provider should initialize with API key."""
        from heisenberg.llm.providers import AnthropicProvider as ClaudeProvider

        provider = ClaudeProvider(api_key=os.environ["ANTHROPIC_API_KEY"])
        assert provider is not None
        assert provider.name == "anthropic"

    @pytest.mark.skipif(not has_anthropic_key(), reason="ANTHROPIC_API_KEY not set")
    @pytest.mark.asyncio
    async def test_claude_provider_analyzes_prompt(self):
        """Claude provider should return analysis for a prompt."""
        from heisenberg.llm.providers import AnthropicProvider as ClaudeProvider

        provider = ClaudeProvider(api_key=os.environ["ANTHROPIC_API_KEY"])
        result = await provider.analyze_async(
            system_prompt="You are a test failure analyst.",
            user_prompt="Why might a login button timeout occur?",
        )

        assert result.content is not None
        assert len(result.content) > 0
        assert result.input_tokens is not None
        assert result.output_tokens is not None
        assert result.input_tokens > 0
        assert result.output_tokens > 0

    @pytest.mark.skipif(not has_anthropic_key(), reason="ANTHROPIC_API_KEY not set")
    @pytest.mark.asyncio
    async def test_claude_provider_returns_model_info(self):
        """Claude provider should return model information."""
        from heisenberg.llm.providers import AnthropicProvider as ClaudeProvider

        provider = ClaudeProvider(api_key=os.environ["ANTHROPIC_API_KEY"])
        result = await provider.analyze_async(
            system_prompt="Respond briefly.",
            user_prompt="Say hello.",
        )

        assert result.model is not None
        assert "claude" in result.model.lower()

    @pytest.mark.skipif(not has_anthropic_key(), reason="ANTHROPIC_API_KEY not set")
    @pytest.mark.asyncio
    async def test_claude_handles_test_failure_context(self):
        """Claude should analyze test failure context meaningfully."""
        from heisenberg.llm.providers import AnthropicProvider as ClaudeProvider

        provider = ClaudeProvider(api_key=os.environ["ANTHROPIC_API_KEY"])

        prompt = f"""
        Analyze this test failure:
        Test: {SAMPLE_FAILED_TEST["name"]}
        Error: {SAMPLE_FAILED_TEST["error_message"]}
        Retries: {SAMPLE_FAILED_TEST["retry_count"]}

        Provide a brief root cause analysis.
        """

        result = await provider.analyze_async(
            system_prompt="You are a test failure analyst. Be concise.",
            user_prompt=prompt,
        )

        response = result.content.lower()
        # Should mention something relevant to the error
        assert any(
            term in response
            for term in ["timeout", "selector", "element", "wait", "login", "button"]
        )


class TestGeminiIntegration:
    """Integration tests for Google Gemini API."""

    @pytest.mark.skipif(not has_google_key(), reason="GOOGLE_API_KEY not set")
    @pytest.mark.asyncio
    async def test_gemini_provider_initializes(self):
        """Gemini provider should initialize with API key."""
        from heisenberg.llm.providers import GeminiProvider

        provider = GeminiProvider(api_key=os.environ["GOOGLE_API_KEY"])
        assert provider is not None
        assert provider.name == "google"

    @pytest.mark.skipif(not has_google_key(), reason="GOOGLE_API_KEY not set")
    @pytest.mark.asyncio
    async def test_gemini_provider_analyzes_prompt(self):
        """Gemini provider should return analysis for a prompt."""
        from heisenberg.llm.providers import GeminiProvider

        provider = GeminiProvider(api_key=os.environ["GOOGLE_API_KEY"])
        result = await provider.analyze_async(
            system_prompt="You are a test failure analyst.",
            user_prompt="Why might a login button timeout occur?",
        )

        assert result.content is not None
        assert len(result.content) > 0
        assert result.input_tokens is not None
        assert result.output_tokens is not None

    @pytest.mark.skipif(not has_google_key(), reason="GOOGLE_API_KEY not set")
    @pytest.mark.asyncio
    async def test_gemini_provider_returns_model_info(self):
        """Gemini provider should return model information."""
        from heisenberg.llm.providers import GeminiProvider

        provider = GeminiProvider(api_key=os.environ["GOOGLE_API_KEY"])
        result = await provider.analyze_async(
            system_prompt="Respond briefly.",
            user_prompt="Say hello.",
        )

        assert result.model is not None
        assert "gemini" in result.model.lower()


class TestOpenAIIntegration:
    """Integration tests for OpenAI API."""

    @pytest.mark.skipif(not has_openai_key(), reason="OPENAI_API_KEY not set")
    @pytest.mark.asyncio
    async def test_openai_provider_initializes(self):
        """OpenAI provider should initialize with API key."""
        from heisenberg.llm.providers import OpenAIProvider

        provider = OpenAIProvider(api_key=os.environ["OPENAI_API_KEY"])
        assert provider is not None
        assert provider.name == "openai"

    @pytest.mark.skipif(not has_openai_key(), reason="OPENAI_API_KEY not set")
    @pytest.mark.asyncio
    async def test_openai_provider_analyzes_prompt(self):
        """OpenAI provider should return analysis for a prompt."""
        from heisenberg.llm.providers import OpenAIProvider

        provider = OpenAIProvider(api_key=os.environ["OPENAI_API_KEY"])
        result = await provider.analyze_async(
            system_prompt="You are a test failure analyst.",
            user_prompt="Why might a login button timeout occur?",
        )

        assert result.content is not None
        assert len(result.content) > 0
        assert result.input_tokens is not None
        assert result.output_tokens is not None

    @pytest.mark.skipif(not has_openai_key(), reason="OPENAI_API_KEY not set")
    @pytest.mark.asyncio
    async def test_openai_provider_returns_model_info(self):
        """OpenAI provider should return model information."""
        from heisenberg.llm.providers import OpenAIProvider

        provider = OpenAIProvider(api_key=os.environ["OPENAI_API_KEY"])
        result = await provider.analyze_async(
            system_prompt="Respond briefly.",
            user_prompt="Say hello.",
        )

        assert result.model is not None
        assert "gpt" in result.model.lower()


class TestLLMRouterIntegration:
    """Integration tests for LLM Router with real providers."""

    @pytest.mark.skipif(not has_anthropic_key(), reason="ANTHROPIC_API_KEY not set")
    @pytest.mark.asyncio
    async def test_router_with_claude_provider(self):
        """Router should work with Claude as primary provider."""
        from heisenberg.llm.providers import AnthropicProvider as ClaudeProvider
        from heisenberg.llm.router import LLMRouter

        provider = ClaudeProvider(api_key=os.environ["ANTHROPIC_API_KEY"])
        router = LLMRouter(providers=[provider])

        result = await router.analyze_async(
            system_prompt="Be brief.",
            user_prompt="What is 2+2?",
        )

        assert result.content is not None
        assert "4" in result.content or "four" in result.content.lower()

    @pytest.mark.skipif(not has_openai_key(), reason="OPENAI_API_KEY not set")
    @pytest.mark.asyncio
    async def test_router_with_openai_provider(self):
        """Router should work with OpenAI as primary provider."""
        from heisenberg.llm.providers import OpenAIProvider
        from heisenberg.llm.router import LLMRouter

        provider = OpenAIProvider(api_key=os.environ["OPENAI_API_KEY"])
        router = LLMRouter(providers=[provider])

        result = await router.analyze_async(
            system_prompt="Be brief.",
            user_prompt="What is 2+2?",
        )

        assert result.content is not None
        assert "4" in result.content or "four" in result.content.lower()

    @pytest.mark.skipif(not has_google_key(), reason="GOOGLE_API_KEY not set")
    @pytest.mark.asyncio
    async def test_router_with_gemini_provider(self):
        """Router should work with Gemini as primary provider."""
        from heisenberg.llm.providers import GeminiProvider
        from heisenberg.llm.router import LLMRouter

        provider = GeminiProvider(api_key=os.environ["GOOGLE_API_KEY"])
        router = LLMRouter(providers=[provider])

        result = await router.analyze_async(
            system_prompt="Be brief.",
            user_prompt="What is 2+2?",
        )

        assert result.content is not None
        assert "4" in result.content or "four" in result.content.lower()

    @pytest.mark.skipif(
        not (has_anthropic_key() and has_openai_key()),
        reason="Both API keys required",
    )
    @pytest.mark.asyncio
    async def test_router_with_fallback(self):
        """Router should support fallback between providers."""
        from heisenberg.llm.providers import AnthropicProvider as ClaudeProvider
        from heisenberg.llm.providers import OpenAIProvider
        from heisenberg.llm.router import LLMRouter

        claude = ClaudeProvider(api_key=os.environ["ANTHROPIC_API_KEY"])
        openai = OpenAIProvider(api_key=os.environ["OPENAI_API_KEY"])
        router = LLMRouter(providers=[claude, openai])

        result = await router.analyze_async(
            system_prompt="Be brief.",
            user_prompt="Say hello.",
        )

        assert result.content is not None
        assert len(result.content) > 0


class TestAnalyzeServiceIntegration:
    """Integration tests for the full AnalyzeService with real LLM."""

    @pytest.mark.skipif(not has_anthropic_key(), reason="ANTHROPIC_API_KEY not set")
    @pytest.mark.asyncio
    async def test_analyze_service_with_real_llm(self):
        """AnalyzeService should produce diagnosis with real LLM."""
        from heisenberg.backend.llm.adapter import LLMRouterAdapter
        from heisenberg.backend.schemas import FailedTest
        from heisenberg.backend.services.analyze import AnalyzeService
        from heisenberg.llm.providers import AnthropicProvider as ClaudeProvider
        from heisenberg.llm.router import LLMRouter

        provider = ClaudeProvider(api_key=os.environ["ANTHROPIC_API_KEY"])
        router = LLMRouter(providers=[provider])
        adapter = LLMRouterAdapter(router)
        service = AnalyzeService(llm_client=adapter)

        failed_test = FailedTest(
            name="test_checkout_flow",
            file="tests/checkout.spec.ts",
            error_message="Element not found: #submit-order",
            stack_trace="at checkout.spec.ts:42",
            duration_ms=15000,
            retry_count=1,
        )

        result = await service.analyze_test_failure(failed_test)

        assert result is not None
        assert result.test_name == "test_checkout_flow"
        assert result.diagnosis is not None
        assert len(result.diagnosis) > 0

    @pytest.mark.skipif(not has_anthropic_key(), reason="ANTHROPIC_API_KEY not set")
    @pytest.mark.asyncio
    async def test_analyze_service_returns_confidence(self):
        """AnalyzeService should return confidence score."""
        from heisenberg.backend.llm.adapter import LLMRouterAdapter
        from heisenberg.backend.schemas import FailedTest
        from heisenberg.backend.services.analyze import AnalyzeService
        from heisenberg.llm.providers import AnthropicProvider as ClaudeProvider
        from heisenberg.llm.router import LLMRouter

        provider = ClaudeProvider(api_key=os.environ["ANTHROPIC_API_KEY"])
        router = LLMRouter(providers=[provider])
        adapter = LLMRouterAdapter(router)
        service = AnalyzeService(llm_client=adapter)

        failed_test = FailedTest(
            name="test_flaky_network",
            file="tests/api.spec.ts",
            error_message="fetch failed: ECONNRESET",
            stack_trace="at api.spec.ts:10",
            duration_ms=5000,
            retry_count=3,
        )

        result = await service.analyze_test_failure(failed_test)

        assert result.confidence is not None
        assert 0.0 <= result.confidence <= 1.0

    @pytest.mark.skipif(not has_anthropic_key(), reason="ANTHROPIC_API_KEY not set")
    @pytest.mark.asyncio
    async def test_analyze_service_detects_flaky_pattern(self):
        """AnalyzeService should detect flaky test patterns."""
        from heisenberg.backend.llm.adapter import LLMRouterAdapter
        from heisenberg.backend.schemas import FailedTest
        from heisenberg.backend.services.analyze import AnalyzeService
        from heisenberg.llm.providers import AnthropicProvider as ClaudeProvider
        from heisenberg.llm.router import LLMRouter

        provider = ClaudeProvider(api_key=os.environ["ANTHROPIC_API_KEY"])
        router = LLMRouter(providers=[provider])
        adapter = LLMRouterAdapter(router)
        service = AnalyzeService(llm_client=adapter)

        # High retry count suggests flakiness
        failed_test = FailedTest(
            name="test_race_condition",
            file="tests/async.spec.ts",
            error_message="Expected 5 but got 4",
            stack_trace="at async.spec.ts:20",
            duration_ms=100,
            retry_count=5,  # Many retries
        )

        result = await service.analyze_test_failure(failed_test)

        # Check if flaky was detected or mentioned in diagnosis
        diagnosis_lower = result.diagnosis.lower()
        is_flaky_mentioned = any(
            term in diagnosis_lower for term in ["flaky", "race", "timing", "intermittent", "retry"]
        )
        assert result.is_flaky or is_flaky_mentioned


class TestReportParsingIntegration:
    """Integration tests for parsing real Playwright reports."""

    def test_parse_sample_report(self, tmp_path):
        """Should parse a sample Playwright JSON report."""
        import json

        from heisenberg.parser.playwright import PlaywrightReportParser

        report_data = {
            "suites": [
                {
                    "title": "Auth Tests",
                    "specs": [
                        {
                            "title": "login test",
                            "tests": [
                                {
                                    "status": "failed",
                                    "results": [
                                        {
                                            "status": "failed",
                                            "duration": 5000,
                                            "error": {
                                                "message": "Login failed",
                                                "stack": "Error at line 10",
                                            },
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ]
        }

        report_file = tmp_path / "report.json"
        report_file.write_text(json.dumps(report_data))

        parser = PlaywrightReportParser()
        result = parser.parse(str(report_file))

        assert result is not None
        assert len(result.failed_tests) > 0

    @pytest.mark.skipif(not has_anthropic_key(), reason="ANTHROPIC_API_KEY not set")
    @pytest.mark.asyncio
    async def test_full_pipeline_parse_and_analyze(self, tmp_path):
        """Full pipeline: parse report and analyze with real LLM."""
        import json

        from heisenberg.backend.llm.adapter import LLMRouterAdapter
        from heisenberg.backend.services.analyze import AnalyzeService
        from heisenberg.llm.providers import AnthropicProvider as ClaudeProvider
        from heisenberg.llm.router import LLMRouter
        from heisenberg.parser.playwright import PlaywrightReportParser

        # Create sample report
        report_data = {
            "suites": [
                {
                    "title": "E2E Tests",
                    "specs": [
                        {
                            "title": "checkout flow",
                            "file": "checkout.spec.ts",
                            "tests": [
                                {
                                    "status": "failed",
                                    "results": [
                                        {
                                            "status": "failed",
                                            "duration": 30000,
                                            "retry": 2,
                                            "error": {
                                                "message": "Timeout waiting for payment confirmation",
                                                "stack": "at checkout.spec.ts:55",
                                            },
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ]
        }

        report_file = tmp_path / "report.json"
        report_file.write_text(json.dumps(report_data))

        # Parse report
        parser = PlaywrightReportParser()
        parsed = parser.parse(str(report_file))

        # Set up analyzer
        provider = ClaudeProvider(api_key=os.environ["ANTHROPIC_API_KEY"])
        router = LLMRouter(providers=[provider])
        adapter = LLMRouterAdapter(router)
        service = AnalyzeService(llm_client=adapter)

        # Analyze each failed test
        results = []
        for failed_test in parsed.failed_tests:
            from heisenberg.backend.schemas import FailedTest

            ft = FailedTest(
                name=failed_test.name,
                file=failed_test.file or "",
                error_message=failed_test.error_message or "",
                stack_trace=failed_test.stack_trace or "",
                duration_ms=failed_test.duration_ms or 0,
                retry_count=failed_test.retry_count or 0,
            )
            result = await service.analyze_test_failure(ft)
            results.append(result)

        assert len(results) > 0
        assert all(r.diagnosis for r in results)
