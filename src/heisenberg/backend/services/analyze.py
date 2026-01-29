"""Analyze service for processing test failure analysis requests.

This service uses the core analysis logic via UnifiedTestRun transformation,
ensuring consistent prompt building and single-LLM-call analysis across
both the backend API and direct library usage.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Protocol

from heisenberg.backend.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    DiagnosisResponse,
    FailedTest,
)
from heisenberg.core.diagnosis import parse_diagnosis
from heisenberg.core.models import (
    ErrorInfo,
    FailureMetadata,
    Framework,
    UnifiedFailure,
    UnifiedTestRun,
)
from heisenberg.llm.prompts import build_unified_prompt

if TYPE_CHECKING:
    from heisenberg.llm.models import LLMAnalysis


class LLMClientProtocol(Protocol):
    """Protocol for LLM client interface."""

    async def analyze(self, prompt: str, system_prompt: str | None = None) -> LLMAnalysis:
        """Analyze prompt with LLM."""
        ...


class AnalyzeService:
    """Service for analyzing test failures with AI.

    Uses core's unified analysis approach for:
    - Single LLM call for all failures (better context, lower cost)
    - Sophisticated prompt building with log compression
    - Consistent analysis quality across API and library usage
    """

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

        Transforms the request to UnifiedTestRun format and uses core's
        prompt building for consistent, high-quality analysis.

        Args:
            request: Analysis request with failed tests.

        Returns:
            Analysis response with diagnoses.
        """
        # Transform to unified model
        unified_run = _request_to_unified_run(request)

        # Build prompts using core's sophisticated prompt builder
        system_prompt, user_prompt = build_unified_prompt(unified_run)

        # Single LLM call for all failures
        response = await self.llm_client.analyze(
            prompt=user_prompt,
            system_prompt=system_prompt,
        )

        # Parse the diagnosis
        diagnosis = parse_diagnosis(response.content)

        # Build test names summary for response
        test_names = [t.title for t in request.failed_tests]
        test_name_summary = (
            test_names[0] if len(test_names) == 1 else f"{len(test_names)} failed tests"
        )

        return AnalyzeResponse(
            test_run_id=uuid.uuid4(),
            repository=request.repository,
            diagnoses=[
                DiagnosisResponse(
                    test_name=test_name_summary,
                    root_cause=diagnosis.root_cause,
                    evidence=diagnosis.evidence,
                    suggested_fix=diagnosis.suggested_fix,
                    confidence=diagnosis.confidence.value,
                    confidence_explanation=diagnosis.confidence_explanation,
                )
            ],
            total_input_tokens=response.input_tokens,
            total_output_tokens=response.output_tokens,
            created_at=datetime.now(UTC),
        )


def _request_to_unified_run(request: AnalyzeRequest) -> UnifiedTestRun:
    """Transform AnalyzeRequest to UnifiedTestRun for core analysis.

    Args:
        request: Backend API request with test failures.

    Returns:
        UnifiedTestRun compatible with core analysis functions.
    """
    failures = [_failed_test_to_unified_failure(ft) for ft in request.failed_tests]

    return UnifiedTestRun(
        run_id=str(uuid.uuid4()),
        repository=request.repository,
        branch=request.branch,
        commit_sha=request.commit_sha,
        total_tests=request.total_tests,
        passed_tests=request.passed_tests,
        failed_tests=len(request.failed_tests),
        skipped_tests=request.skipped_tests,
        failures=failures,
    )


def _failed_test_to_unified_failure(failed_test: FailedTest) -> UnifiedFailure:
    """Transform FailedTest schema to UnifiedFailure model.

    Args:
        failed_test: Pydantic schema from API request.

    Returns:
        UnifiedFailure for core analysis.
    """
    # Combine multiple errors into single ErrorInfo
    if failed_test.errors:
        messages = [e.message for e in failed_test.errors]
        stacks = [e.stack for e in failed_test.errors if e.stack]
        error_message = "\n---\n".join(messages) if len(messages) > 1 else messages[0]
        stack_trace = "\n---\n".join(stacks) if stacks else None
    else:
        error_message = "Unknown error"
        stack_trace = None

    # Generate deterministic test ID
    test_id = hashlib.md5(  # noqa: S324 - MD5 for fingerprinting, not security
        f"{failed_test.file or ''}-{failed_test.title}".encode()
    ).hexdigest()[:12]

    return UnifiedFailure(
        test_id=test_id,
        file_path=failed_test.file or "",
        test_title=failed_test.title,
        suite_path=[failed_test.suite] if failed_test.suite else [],
        error=ErrorInfo(
            message=error_message,
            stack_trace=stack_trace,
        ),
        metadata=FailureMetadata(
            framework=Framework.PLAYWRIGHT,  # Default; could be extended
            browser=failed_test.project,
            duration_ms=failed_test.duration_ms or None,
        ),
    )
