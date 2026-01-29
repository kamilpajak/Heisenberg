"""Analysis module - orchestrates AI-powered test failure diagnosis.

This module combines parsers, LLM providers, and integrations to analyze
test failures and produce actionable diagnoses.
"""

from heisenberg.analysis.ai_analyzer import (
    HEISENBERG_AI_MARKER,
    AIAnalysisResult,
    AIAnalyzer,
    analyze_unified_run,
    analyze_with_ai,
)
from heisenberg.analysis.pipeline import (
    AnalysisResult,
    Analyzer,
    format_pr_comment,
    run_analysis,
)

__all__ = [
    # AI analysis
    "AIAnalysisResult",
    "AIAnalyzer",
    "HEISENBERG_AI_MARKER",
    "analyze_unified_run",
    "analyze_with_ai",
    # Pipeline
    "AnalysisResult",
    "Analyzer",
    "format_pr_comment",
    "run_analysis",
]
