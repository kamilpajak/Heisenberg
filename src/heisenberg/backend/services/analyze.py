"""Analyze service for processing test failure analysis requests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Protocol

from heisenberg.backend.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    DiagnosisResponse,
)
from heisenberg.core.diagnosis import parse_diagnosis
from heisenberg.llm.prompts import get_system_prompt

if TYPE_CHECKING:
    from heisenberg.llm.client import LLMResponse


class LLMClientProtocol(Protocol):
    """Protocol for LLM client interface."""

    async def analyze(self, prompt: str, system_prompt: str | None = None) -> LLMResponse:
        """Analyze prompt with LLM."""
        ...


class AnalyzeService:
    """Service for analyzing test failures with AI."""

    def __init__(self, llm_client: LLMClientProtocol):
        """
        Initialize analyze service.

        Args:
            llm_client: LLM client for AI analysis.
        """
        self.llm_client = llm_client

    async def analyze(self, request: AnalyzeRequest) -> AnalyzeResponse:
        """
        Analyze test failures and generate diagnoses.

        Args:
            request: Analysis request with failed tests.

        Returns:
            Analysis response with diagnoses.
        """
        diagnoses: list[DiagnosisResponse] = []
        total_input_tokens = 0
        total_output_tokens = 0

        for failed_test in request.failed_tests:
            # Build prompt for this test
            prompt = self._build_prompt_for_test(failed_test, request)

            # Get AI analysis
            response = await self.llm_client.analyze(
                prompt=prompt,
                system_prompt=get_system_prompt(),
            )

            total_input_tokens += response.input_tokens
            total_output_tokens += response.output_tokens

            # Parse the diagnosis
            diagnosis = parse_diagnosis(response.content)

            diagnoses.append(
                DiagnosisResponse(
                    test_name=failed_test.title,
                    root_cause=diagnosis.root_cause,
                    evidence=diagnosis.evidence,
                    suggested_fix=diagnosis.suggested_fix,
                    confidence=diagnosis.confidence.value,
                    confidence_explanation=diagnosis.confidence_explanation,
                )
            )

        return AnalyzeResponse(
            test_run_id=uuid.uuid4(),
            repository=request.repository,
            diagnoses=diagnoses,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            created_at=datetime.now(UTC),
        )

    def _build_prompt_for_test(
        self,
        failed_test,
        request: AnalyzeRequest,
    ) -> str:
        """
        Build analysis prompt for a single failed test.

        Args:
            failed_test: The failed test to analyze.
            request: Full analysis request for context.

        Returns:
            Formatted prompt string.
        """
        lines = [
            "# Test Failure Analysis Request",
            "",
            f"## Repository: {request.repository}",
            "",
            "## Failed Test",
            f"- **Name:** {failed_test.title}",
        ]

        if failed_test.file:
            lines.append(f"- **File:** {failed_test.file}")
        if failed_test.suite:
            lines.append(f"- **Suite:** {failed_test.suite}")
        if failed_test.duration_ms:
            lines.append(f"- **Duration:** {failed_test.duration_ms}ms")

        if failed_test.errors:
            lines.append("")
            lines.append("## Errors")
            for i, error in enumerate(failed_test.errors, 1):
                lines.append(f"### Error {i}")
                lines.append(f"**Message:** {error.message}")
                if error.stack:
                    lines.append(f"**Stack:** {error.stack}")

        if request.container_logs:
            lines.append("")
            lines.append("## Backend Logs")
            for container_log in request.container_logs:
                lines.append(f"### Container: {container_log.container_name}")
                for entry in container_log.entries[:20]:  # Limit entries
                    lines.append(f"[{entry.timestamp}] {entry.message}")

        lines.append("")
        lines.append("Please analyze this test failure and provide your diagnosis.")

        return "\n".join(lines)
