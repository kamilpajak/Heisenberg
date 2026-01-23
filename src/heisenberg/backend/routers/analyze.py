"""API router for /analyze endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from heisenberg.backend.auth import get_api_key
from heisenberg.backend.schemas import AnalyzeRequest, AnalyzeResponse

router = APIRouter(prefix="/analyze", tags=["Analysis"])


@router.post(
    "/",
    response_model=AnalyzeResponse,
    summary="Analyze test failures",
    description="Submit test failure data for AI-powered root cause analysis.",
)
async def analyze_failures(
    request: AnalyzeRequest,
    api_key: Annotated[str, Depends(get_api_key)],
) -> AnalyzeResponse:
    """
    Analyze test failures with AI.

    Args:
        request: Analysis request containing failed tests and optional logs.
        api_key: API key for authentication.

    Returns:
        Analysis response with AI-generated diagnoses.
    """
    # In production, this would:
    # 1. Validate API key against database
    # 2. Create AnalyzeService with real LLM client
    # 3. Save results to database
    #
    # For now, raise an error indicating backend not fully configured
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Backend analysis not yet configured. Use direct AI analysis in the GitHub Action.",
    )
