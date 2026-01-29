"""Analyze frozen cases with AI-powered diagnosis.

This module runs Heisenberg AI analysis on frozen case data
and saves the diagnosis for use in the demo playground.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from heisenberg.analysis import AIAnalyzer
from heisenberg.parsers.playwright import parse_playwright_report


@dataclass
class AnalyzeConfig:
    """Configuration for analyzing a frozen case."""

    case_dir: Path
    provider: str = "anthropic"
    model: str | None = None
    api_key: str | None = None


@dataclass
class AnalysisResult:
    """Result of analyzing a frozen case."""

    repo: str
    run_id: int
    root_cause: str
    evidence: list[str]
    suggested_fix: str
    confidence: str
    confidence_explanation: str | None
    input_tokens: int
    output_tokens: int
    provider: str
    model: str | None
    analyzed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "repo": self.repo,
            "run_id": self.run_id,
            "diagnosis": {
                "root_cause": self.root_cause,
                "evidence": self.evidence,
                "suggested_fix": self.suggested_fix,
                "confidence": self.confidence,
                "confidence_explanation": self.confidence_explanation,
            },
            "tokens": {
                "input": self.input_tokens,
                "output": self.output_tokens,
                "total": self.input_tokens + self.output_tokens,
            },
            "provider": self.provider,
            "model": self.model,
            "analyzed_at": self.analyzed_at,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


class ScenarioAnalyzer:
    """Analyzes frozen cases using Heisenberg AI."""

    def __init__(self, config: AnalyzeConfig):
        """Initialize analyzer with configuration.

        Args:
            config: AnalyzeConfig with case_dir and optional settings.
        """
        self.config = config

    def load_metadata(self) -> dict[str, Any]:
        """Load metadata.json from case directory.

        Returns:
            Parsed metadata dictionary.

        Raises:
            FileNotFoundError: If metadata.json doesn't exist.
        """
        metadata_path = self.config.case_dir / "metadata.json"
        if not metadata_path.exists():
            raise FileNotFoundError(f"metadata.json not found in {self.config.case_dir}")
        return json.loads(metadata_path.read_text())

    def load_report(self) -> dict[str, Any]:
        """Load report.json from case directory.

        Returns:
            Parsed report dictionary.

        Raises:
            FileNotFoundError: If report.json doesn't exist.
        """
        report_path = self.config.case_dir / "report.json"
        if not report_path.exists():
            raise FileNotFoundError(f"report.json not found in {self.config.case_dir}")
        return json.loads(report_path.read_text())

    def analyze(self) -> AnalysisResult:
        """Run AI analysis on the frozen case.

        Returns:
            AnalysisResult with diagnosis and metadata.

        Raises:
            FileNotFoundError: If case files are missing.
            ValueError: If report is invalid or AI analysis fails.
        """
        # Load case data
        metadata = self.load_metadata()

        # Parse report from file
        report_path = self.config.case_dir / "report.json"
        report = parse_playwright_report(report_path)

        # Run AI analysis
        ai_analyzer = AIAnalyzer(
            report=report,
            provider=self.config.provider,
            model=self.config.model,
            api_key=self.config.api_key,
        )
        ai_result = ai_analyzer.analyze()

        # Build result
        analyzed_at = datetime.now(UTC).isoformat()
        result = AnalysisResult(
            repo=metadata["repo"],
            run_id=metadata["run_id"],
            root_cause=ai_result.diagnosis.root_cause,
            evidence=ai_result.diagnosis.evidence,
            suggested_fix=ai_result.diagnosis.suggested_fix,
            confidence=ai_result.diagnosis.confidence.value,
            confidence_explanation=ai_result.diagnosis.confidence_explanation,
            input_tokens=ai_result.input_tokens,
            output_tokens=ai_result.output_tokens,
            provider=ai_result.provider,
            model=ai_result.model,
            analyzed_at=analyzed_at,
        )

        # Save diagnosis to file
        self._save_diagnosis(result)

        return result

    def _save_diagnosis(self, result: AnalysisResult) -> Path:
        """Save diagnosis to diagnosis.json in case directory.

        Args:
            result: Analysis result to save.

        Returns:
            Path to saved diagnosis file.
        """
        diagnosis_path = self.config.case_dir / "diagnosis.json"
        diagnosis_path.write_text(result.to_json())
        return diagnosis_path
