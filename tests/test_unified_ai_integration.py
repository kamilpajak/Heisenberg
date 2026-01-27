"""Tests for UnifiedModel integration with AI Analyzer.

These tests verify that the AI analysis pipeline works with the
unified failure model, enabling framework-agnostic analysis.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from heisenberg.core.models import (
    ErrorInfo,
    FailureMetadata,
    Framework,
    UnifiedFailure,
    UnifiedTestRun,
)


class TestUnifiedPromptBuilder:
    """Tests for building AI prompts from UnifiedTestRun."""

    def test_build_prompt_from_unified_run(self):
        """Prompt builder creates valid prompt from UnifiedTestRun."""
        from heisenberg.llm.prompts import build_unified_prompt

        run = UnifiedTestRun(
            run_id="test-run-123",
            repository="owner/repo",
            branch="main",
            total_tests=10,
            passed_tests=8,
            failed_tests=2,
            skipped_tests=0,
            failures=[
                UnifiedFailure(
                    test_id="1",
                    file_path="tests/login.spec.ts",
                    test_title="should login successfully",
                    error=ErrorInfo(
                        message="Timeout waiting for selector '#submit'",
                        stack_trace="at login.spec.ts:15:5",
                    ),
                    metadata=FailureMetadata(
                        framework=Framework.PLAYWRIGHT,
                        browser="chromium",
                        duration_ms=30000,
                    ),
                ),
            ],
        )

        system_prompt, user_prompt = build_unified_prompt(run)

        # System prompt should contain role instructions
        assert "test failure" in system_prompt.lower()
        assert "diagnosis" in system_prompt.lower() or "analyze" in system_prompt.lower()

        # User prompt should contain failure details
        assert "login.spec.ts" in user_prompt
        assert "should login successfully" in user_prompt
        assert "Timeout" in user_prompt
        assert "#submit" in user_prompt

    def test_build_prompt_includes_summary(self):
        """Prompt includes test run summary statistics."""
        from heisenberg.llm.prompts import build_unified_prompt

        run = UnifiedTestRun(
            run_id="run-1",
            total_tests=100,
            passed_tests=95,
            failed_tests=3,
            skipped_tests=2,
            failures=[
                UnifiedFailure(
                    test_id="1",
                    file_path="test.ts",
                    test_title="test 1",
                    error=ErrorInfo(message="Error 1"),
                ),
            ],
        )

        _, user_prompt = build_unified_prompt(run)

        assert "100" in user_prompt  # total
        assert "95" in user_prompt  # passed
        assert "3" in user_prompt  # failed

    def test_build_prompt_includes_metadata(self):
        """Prompt includes test metadata like browser and framework."""
        from heisenberg.llm.prompts import build_unified_prompt

        run = UnifiedTestRun(
            run_id="run-1",
            repository="microsoft/playwright",
            branch="feature/fix",
            total_tests=10,
            passed_tests=9,
            failed_tests=1,
            skipped_tests=0,
            failures=[
                UnifiedFailure(
                    test_id="1",
                    file_path="test.ts",
                    test_title="browser test",
                    error=ErrorInfo(message="Failed"),
                    metadata=FailureMetadata(
                        framework=Framework.PLAYWRIGHT,
                        browser="firefox",
                    ),
                ),
            ],
        )

        _, user_prompt = build_unified_prompt(run)

        assert "firefox" in user_prompt.lower()
        assert "playwright" in user_prompt.lower()

    def test_build_prompt_multiple_failures(self):
        """Prompt includes all failures when multiple exist."""
        from heisenberg.llm.prompts import build_unified_prompt

        run = UnifiedTestRun(
            run_id="run-1",
            total_tests=10,
            passed_tests=7,
            failed_tests=3,
            skipped_tests=0,
            failures=[
                UnifiedFailure(
                    test_id="1",
                    file_path="auth.spec.ts",
                    test_title="login test",
                    error=ErrorInfo(message="Login timeout"),
                ),
                UnifiedFailure(
                    test_id="2",
                    file_path="cart.spec.ts",
                    test_title="checkout test",
                    error=ErrorInfo(message="Cart empty error"),
                ),
                UnifiedFailure(
                    test_id="3",
                    file_path="profile.spec.ts",
                    test_title="profile test",
                    error=ErrorInfo(message="Profile not found"),
                ),
            ],
        )

        _, user_prompt = build_unified_prompt(run)

        assert "auth.spec.ts" in user_prompt
        assert "cart.spec.ts" in user_prompt
        assert "profile.spec.ts" in user_prompt
        assert "Login timeout" in user_prompt
        assert "Cart empty error" in user_prompt


class TestUnifiedAIAnalyzer:
    """Tests for AI analyzer with UnifiedTestRun input."""

    def test_analyze_unified_run(self):
        """AI analyzer accepts UnifiedTestRun and returns diagnosis."""
        from heisenberg.core.analyzer import analyze_unified_run

        run = UnifiedTestRun(
            run_id="test-123",
            total_tests=5,
            passed_tests=4,
            failed_tests=1,
            skipped_tests=0,
            failures=[
                UnifiedFailure(
                    test_id="1",
                    file_path="test.spec.ts",
                    test_title="should work",
                    error=ErrorInfo(message="Element not found"),
                    metadata=FailureMetadata(framework=Framework.PLAYWRIGHT),
                ),
            ],
        )

        with patch("heisenberg.core.analyzer._get_llm_client_for_provider") as mock_get_client:
            mock_client = MagicMock()
            mock_client.analyze.return_value = MagicMock(
                content="""
                ## Root Cause
                Element selector issue

                ## Evidence
                - Selector not found in DOM

                ## Suggested Fix
                Update selector

                ## Confidence
                HIGH
                """,
                input_tokens=100,
                output_tokens=50,
            )
            mock_get_client.return_value = mock_client

            result = analyze_unified_run(run)

            assert result.diagnosis.root_cause is not None
            assert result.input_tokens == 100
            assert result.output_tokens == 50

    def test_analyze_unified_with_provider(self):
        """AI analyzer respects provider parameter."""
        from heisenberg.core.analyzer import analyze_unified_run

        run = UnifiedTestRun(
            run_id="test-123",
            total_tests=1,
            passed_tests=0,
            failed_tests=1,
            skipped_tests=0,
            failures=[
                UnifiedFailure(
                    test_id="1",
                    file_path="test.ts",
                    test_title="test",
                    error=ErrorInfo(message="Error"),
                ),
            ],
        )

        with patch("heisenberg.core.analyzer._get_llm_client_for_provider") as mock_get_client:
            mock_client = MagicMock()
            mock_client.analyze.return_value = MagicMock(
                content="## Root Cause\nTest\n## Evidence\n- E\n## Suggested Fix\nF\n## Confidence\nHIGH",
                input_tokens=10,
                output_tokens=5,
            )
            mock_get_client.return_value = mock_client

            analyze_unified_run(run, provider="anthropic")

            mock_get_client.assert_called_with("anthropic", None, None)


class TestEndToEndUnifiedFlow:
    """End-to-end tests for unified model flow."""

    def test_playwright_to_unified_to_analysis(self):
        """Full flow: Playwright report -> UnifiedTestRun -> AI Analysis."""
        from heisenberg.core.analyzer import analyze_unified_run
        from heisenberg.core.models import PlaywrightTransformer
        from heisenberg.parsers.playwright import ErrorDetail, FailedTest, PlaywrightReport

        # 1. Create Playwright report
        report = PlaywrightReport(
            total_passed=9,
            total_failed=1,
            total_skipped=0,
            total_flaky=0,
            failed_tests=[
                FailedTest(
                    title="checkout flow",
                    file="checkout.spec.ts",
                    suite="E2E",
                    project="chromium",
                    status="failed",
                    duration_ms=5000,
                    start_time=None,
                    errors=[
                        ErrorDetail(
                            message="Payment button not clickable",
                            stack="at checkout.spec.ts:42",
                        )
                    ],
                )
            ],
        )

        # 2. Transform to unified model
        unified_run = PlaywrightTransformer.transform_report(
            report,
            run_id="github-run-456",
            repository="shop/frontend",
        )

        assert unified_run.run_id == "github-run-456"
        assert len(unified_run.failures) == 1
        assert unified_run.failures[0].error.message == "Payment button not clickable"

        # 3. Analyze with AI (mocked)
        with patch("heisenberg.core.analyzer._get_llm_client_for_provider") as mock_get_client:
            mock_client = MagicMock()
            mock_client.analyze.return_value = MagicMock(
                content="""
                ## Root Cause
                Button disabled due to validation error

                ## Evidence
                - Payment form validation failing

                ## Suggested Fix
                Check form validation state before clicking

                ## Confidence
                MEDIUM
                """,
                input_tokens=200,
                output_tokens=100,
            )
            mock_get_client.return_value = mock_client

            result = analyze_unified_run(unified_run)

            assert "validation" in result.diagnosis.root_cause.lower()
