"""Screenshot analysis for Playwright test failures.

This module extracts screenshots from Playwright artifacts and uses
vision-capable LLMs to describe what's visible, providing additional
context for failure diagnosis.
"""

from __future__ import annotations

import base64
import io
import os
import zipfile
from dataclasses import dataclass

from heisenberg.artifact_utils import extract_spec_file_from_path, extract_test_name_from_path

# Default model for screenshot analysis
DEFAULT_VISION_MODEL = "gemini-2.0-flash"


@dataclass
class ScreenshotContext:
    """Context for a screenshot from a failed test."""

    test_name: str
    file_path: str
    image_data: bytes
    description: str | None

    def to_base64(self) -> str:
        """Convert image data to base64 string."""
        return base64.b64encode(self.image_data).decode("utf-8")

    def format_for_prompt(self) -> str:
        """Format screenshot context for inclusion in prompt."""
        lines = [f"**Test: {self.test_name}** ({self.file_path})"]
        if self.description:
            lines.append(self.description)
        else:
            lines.append("*Screenshot available but not analyzed*")
        return "\n".join(lines)


def extract_screenshots_from_artifact(zip_data: bytes) -> list[ScreenshotContext]:
    """Extract screenshot files from Playwright artifact ZIP.

    Args:
        zip_data: Raw bytes of the artifact ZIP file.

    Returns:
        List of ScreenshotContext objects with image data.
    """
    screenshots = []

    try:
        with zipfile.ZipFile(io.BytesIO(zip_data), "r") as zf:
            for file_info in zf.filelist:
                name = file_info.filename.lower()

                # Only process PNG/JPEG screenshots
                if not (name.endswith(".png") or name.endswith(".jpg") or name.endswith(".jpeg")):
                    continue

                # Skip trace screenshots and other non-failure screenshots
                if "trace" in name and "screenshot" not in name:
                    continue

                # Extract test name from path
                # Typical path: test-results/test-name/screenshot.png
                # or: playwright-report/data/test-results/browser/tests/file.spec.ts/test-name/screenshot.png
                path_parts = file_info.filename.split("/")
                test_name = extract_test_name_from_path(path_parts)
                file_path = extract_spec_file_from_path(path_parts)

                # Read image data
                image_data = zf.read(file_info.filename)

                screenshots.append(
                    ScreenshotContext(
                        test_name=test_name,
                        file_path=file_path,
                        image_data=image_data,
                        description=None,
                    )
                )

    except zipfile.BadZipFile:
        pass

    return screenshots


class ScreenshotAnalyzer:
    """Analyzes screenshots using vision-capable LLMs."""

    DEFAULT_PROMPT = """Analyze this screenshot from a failed Playwright test.

Describe what you see on the page:
1. What UI elements are visible?
2. Are there any error messages, alerts, or unexpected states?
3. Does the page appear to be loading, blank, or broken?
4. Any visible text that might indicate the failure cause?

Keep your description concise (2-4 sentences) and focus on details relevant to debugging."""

    def __init__(
        self,
        provider: str = "google",
        api_key: str | None = None,
        model: str | None = None,
    ):
        """Initialize the analyzer.

        Args:
            provider: LLM provider (google recommended for vision).
            api_key: Optional API key.
            model: Optional specific model name.
        """
        self.provider = provider
        self.api_key = api_key
        self.model = model

    def get_analysis_prompt(self) -> str:
        """Get the prompt used for screenshot analysis."""
        return self.DEFAULT_PROMPT

    def analyze(self, screenshot: ScreenshotContext) -> ScreenshotContext:
        """Analyze a single screenshot.

        Args:
            screenshot: ScreenshotContext with image data.

        Returns:
            ScreenshotContext with description filled in.
        """
        try:
            # Get API key
            api_key = self.api_key
            if not api_key:
                api_key = os.environ.get("GOOGLE_API_KEY")

            if not api_key:
                screenshot.description = "[Screenshot analysis skipped: No API key]"
                return screenshot

            # Use Gemini for vision analysis
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            model = self.model or DEFAULT_VISION_MODEL

            # Create image part
            image_part = types.Part.from_bytes(
                data=screenshot.image_data,
                mime_type="image/png",
            )

            # Generate content with image
            response = client.models.generate_content(
                model=model,
                contents=[self.get_analysis_prompt(), image_part],
            )

            screenshot.description = response.text

        except Exception as e:
            screenshot.description = f"[Screenshot analysis failed: {e}]"

        return screenshot

    def analyze_batch(
        self,
        screenshots: list[ScreenshotContext],
        max_screenshots: int = 5,
    ) -> list[ScreenshotContext]:
        """Analyze multiple screenshots.

        Args:
            screenshots: List of ScreenshotContext objects.
            max_screenshots: Maximum number to analyze (to control costs).

        Returns:
            List of ScreenshotContext with descriptions.
        """
        results = []

        for screenshot in screenshots[:max_screenshots]:
            result = self.analyze(screenshot)
            results.append(result)

        # Add remaining screenshots without analysis
        for screenshot in screenshots[max_screenshots:]:
            screenshot.description = "[Screenshot not analyzed: limit reached]"
            results.append(screenshot)

        return results


def format_screenshots_for_prompt(screenshots: list[ScreenshotContext]) -> str:
    """Format screenshot contexts for inclusion in AI prompt.

    Args:
        screenshots: List of analyzed ScreenshotContext objects.

    Returns:
        Formatted string for prompt, or empty string if no screenshots.
    """
    if not screenshots:
        return ""

    lines = ["### Screenshot Analysis:"]

    for screenshot in screenshots:
        lines.append("")
        lines.append(screenshot.format_for_prompt())

    return "\n".join(lines)
