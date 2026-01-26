"""Tests for screenshot analysis with vision models.

These tests verify that Heisenberg can extract and analyze screenshots
from Playwright test failures using vision-capable LLMs.
"""

from __future__ import annotations

import base64
from unittest.mock import MagicMock, patch

from heisenberg.screenshot_analyzer import (
    ScreenshotAnalyzer,
    ScreenshotContext,
    extract_screenshots_from_artifact,
)


class TestScreenshotExtraction:
    """Tests for extracting screenshots from Playwright artifacts."""

    def test_extract_screenshots_from_zip(self, tmp_path):
        """Extract screenshot files from artifact ZIP."""
        import io
        import zipfile

        # Create a mock ZIP with screenshots
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("test-results/test-login/screenshot.png", b"fake-png-data")
            zf.writestr("test-results/test-logout/failure.png", b"fake-png-data-2")
            zf.writestr("test-results/test-home/trace.zip", b"not-a-screenshot")

        zip_data = zip_buffer.getvalue()
        screenshots = extract_screenshots_from_artifact(zip_data)

        assert len(screenshots) == 2
        assert any("test-login" in s.test_name for s in screenshots)
        assert any("test-logout" in s.test_name for s in screenshots)

    def test_extract_screenshots_handles_nested_dirs(self, tmp_path):
        """Handle deeply nested screenshot paths."""
        import io
        import zipfile

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr(
                "playwright-report/data/test-results/chromium/tests/auth.spec.ts/login-test/screenshot.png",
                b"png-data",
            )

        zip_data = zip_buffer.getvalue()
        screenshots = extract_screenshots_from_artifact(zip_data)

        assert len(screenshots) == 1
        assert (
            "login" in screenshots[0].test_name.lower()
            or "auth" in screenshots[0].test_name.lower()
        )

    def test_extract_no_screenshots_returns_empty(self):
        """Return empty list when no screenshots in artifact."""
        import io
        import zipfile

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("report.json", b"{}")
            zf.writestr("trace.zip", b"trace-data")

        zip_data = zip_buffer.getvalue()
        screenshots = extract_screenshots_from_artifact(zip_data)

        assert len(screenshots) == 0


class TestScreenshotContext:
    """Tests for ScreenshotContext dataclass."""

    def test_screenshot_context_properties(self):
        """ScreenshotContext should have required properties."""
        ctx = ScreenshotContext(
            test_name="login-test",
            file_path="tests/auth.spec.ts",
            image_data=b"png-bytes",
            description=None,
        )

        assert ctx.test_name == "login-test"
        assert ctx.file_path == "tests/auth.spec.ts"
        assert ctx.image_data == b"png-bytes"
        assert ctx.description is None

    def test_screenshot_to_base64(self):
        """Convert screenshot to base64 for API calls."""
        ctx = ScreenshotContext(
            test_name="test",
            file_path="test.ts",
            image_data=b"hello-world",
            description=None,
        )

        b64 = ctx.to_base64()

        assert b64 == base64.b64encode(b"hello-world").decode("utf-8")

    def test_screenshot_format_for_prompt(self):
        """Format screenshot context for text prompt."""
        ctx = ScreenshotContext(
            test_name="login-failure",
            file_path="tests/auth.spec.ts",
            image_data=b"png",
            description="The page shows a login form with an error message 'Invalid credentials'",
        )

        formatted = ctx.format_for_prompt()

        assert "login-failure" in formatted
        assert "Invalid credentials" in formatted


class TestScreenshotAnalyzer:
    """Tests for analyzing screenshots with vision models."""

    @patch("google.genai.Client")
    def test_analyze_screenshot_with_vision_model(self, mock_client_class):
        """Analyze screenshot using vision-capable LLM."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "The screenshot shows a login page with an error banner."
        mock_client.models.generate_content.return_value = mock_response
        mock_client_class.return_value = mock_client

        analyzer = ScreenshotAnalyzer(provider="google", api_key="test-key")
        ctx = ScreenshotContext(
            test_name="login-test",
            file_path="auth.spec.ts",
            image_data=b"fake-png",
            description=None,
        )

        result = analyzer.analyze(ctx)

        assert result.description is not None
        assert "login" in result.description.lower() or "error" in result.description.lower()
        mock_client.models.generate_content.assert_called_once()

    @patch("google.genai.Client")
    def test_analyze_multiple_screenshots(self, mock_client_class):
        """Analyze multiple screenshots in batch."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Screenshot description"
        mock_client.models.generate_content.return_value = mock_response
        mock_client_class.return_value = mock_client

        analyzer = ScreenshotAnalyzer(provider="google", api_key="test-key")
        screenshots = [
            ScreenshotContext("test1", "file1.ts", b"png1", None),
            ScreenshotContext("test2", "file2.ts", b"png2", None),
            ScreenshotContext("test3", "file3.ts", b"png3", None),
        ]

        results = analyzer.analyze_batch(screenshots)

        assert len(results) == 3
        assert all(r.description is not None for r in results)

    @patch("google.genai.Client")
    def test_analyzer_handles_api_error(self, mock_client_class):
        """Handle API errors gracefully."""
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("API rate limit")
        mock_client_class.return_value = mock_client

        analyzer = ScreenshotAnalyzer(provider="google", api_key="test-key")
        ctx = ScreenshotContext("test", "file.ts", b"png", None)

        result = analyzer.analyze(ctx)

        # Should return context with error description, not raise
        assert result.description is not None
        assert "error" in result.description.lower() or "failed" in result.description.lower()

    def test_analyzer_default_prompt(self):
        """Analyzer should use appropriate prompt for test screenshots."""
        analyzer = ScreenshotAnalyzer(provider="google")

        prompt = analyzer.get_analysis_prompt()

        assert "test" in prompt.lower() or "failure" in prompt.lower()
        assert "describe" in prompt.lower() or "analyze" in prompt.lower()


class TestScreenshotPromptIntegration:
    """Tests for integrating screenshots into analysis prompts."""

    def test_format_screenshots_for_prompt(self):
        """Format multiple screenshot descriptions for AI prompt."""
        from heisenberg.screenshot_analyzer import format_screenshots_for_prompt

        screenshots = [
            ScreenshotContext(
                "login-test",
                "auth.spec.ts",
                b"png1",
                "Login form with error: 'Invalid password'",
            ),
            ScreenshotContext(
                "checkout-test",
                "cart.spec.ts",
                b"png2",
                "Empty cart page, expected items missing",
            ),
        ]

        formatted = format_screenshots_for_prompt(screenshots)

        assert "### Screenshot Analysis:" in formatted
        assert "login-test" in formatted
        assert "Invalid password" in formatted
        assert "checkout-test" in formatted
        assert "Empty cart" in formatted

    def test_format_empty_screenshots(self):
        """Return empty string when no screenshots."""
        from heisenberg.screenshot_analyzer import format_screenshots_for_prompt

        formatted = format_screenshots_for_prompt([])

        assert formatted == ""

    def test_prompt_builder_accepts_screenshot_context(self):
        """Prompt builder should include screenshot descriptions."""
        from heisenberg.prompt_builder import build_unified_prompt
        from heisenberg.unified_model import (
            ErrorInfo,
            UnifiedFailure,
            UnifiedTestRun,
        )

        failure = UnifiedFailure(
            test_id="1",
            file_path="tests/auth.spec.ts",
            test_title="login test",
            error=ErrorInfo(message="Element not found"),
        )

        test_run = UnifiedTestRun(
            run_id="test-123",
            total_tests=10,
            passed_tests=9,
            failed_tests=1,
            skipped_tests=0,
            failures=[failure],
        )

        screenshot_context = """### Screenshot Analysis:

**Test: login-test** (auth.spec.ts)
The page shows a blank white screen with no login form visible."""

        system_prompt, user_prompt = build_unified_prompt(
            test_run,
            screenshot_context=screenshot_context,
        )

        assert "Screenshot Analysis" in user_prompt
        assert "blank white screen" in user_prompt
