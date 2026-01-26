"""Diagnosis parser for extracting structured data from LLM responses."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class ConfidenceLevel(Enum):
    """Confidence level for AI diagnosis."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


@dataclass
class Diagnosis:
    """Structured diagnosis from LLM analysis."""

    root_cause: str
    evidence: list[str]
    suggested_fix: str
    confidence: ConfidenceLevel
    raw_response: str
    confidence_explanation: str | None = None


def parse_diagnosis(response: str) -> Diagnosis:
    """
    Parse LLM response into structured Diagnosis.

    Args:
        response: Raw LLM response text.

    Returns:
        Diagnosis with extracted sections.
    """
    root_cause = _extract_section(response, "Root Cause Analysis", "Evidence")
    evidence = _extract_evidence(response)
    suggested_fix = _extract_section(response, "Suggested Fix", "Confidence")
    confidence, confidence_explanation = _extract_confidence(response)

    return Diagnosis(
        root_cause=root_cause or _extract_fallback_root_cause(response),
        evidence=evidence,
        suggested_fix=suggested_fix or _extract_fallback_fix(response),
        confidence=confidence,
        confidence_explanation=confidence_explanation,
        raw_response=response,
    )


def _extract_section(response: str, start_header: str, end_header: str) -> str:
    """Extract content between two section headers."""
    # Pattern to match section content
    pattern = rf"##\s*{start_header}\s*\n(.*?)(?=##\s*{end_header}|$)"
    match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)

    if match:
        return match.group(1).strip()
    return ""


def _extract_evidence(response: str) -> list[str]:
    """Extract evidence items from response."""
    evidence_section = _extract_section(response, "Evidence", "Suggested Fix")

    if not evidence_section:
        return []

    # Extract bullet points (lines starting with - or *)
    evidence = []
    for line in evidence_section.split("\n"):
        line = line.strip()
        if line.startswith(("-", "*")):
            evidence.append(line[1:].strip())

    return evidence


def _extract_confidence(response: str) -> tuple[ConfidenceLevel, str | None]:
    """Extract confidence level and explanation from response."""
    confidence_text = _find_confidence_section(response)

    if not confidence_text:
        return ConfidenceLevel.UNKNOWN, None

    confidence_text = confidence_text.strip()
    level = _determine_confidence_level(confidence_text)
    explanation = _extract_confidence_explanation(confidence_text)

    return level, explanation


def _find_confidence_section(response: str) -> str:
    """Find confidence section using various header patterns."""
    headers = ["Confidence", "Confidence Score", "Confidence Level"]
    for header in headers:
        section = _extract_section(response, header, "##")
        if section:
            return section
    return ""


def _determine_confidence_level(text: str) -> ConfidenceLevel:
    """Determine confidence level from text content."""
    upper_text = text.upper()
    level_mapping = [
        ("HIGH", ConfidenceLevel.HIGH),
        ("MEDIUM", ConfidenceLevel.MEDIUM),
        ("LOW", ConfidenceLevel.LOW),
    ]
    for keyword, level in level_mapping:
        if keyword in upper_text:
            return level
    return ConfidenceLevel.UNKNOWN


def _extract_confidence_explanation(text: str) -> str | None:
    """Extract explanation text after confidence level line."""
    lines = text.split("\n")
    explanation_lines = []
    found_level = False

    for line in lines:
        if _line_contains_level(line):
            found_level = True
            continue
        if found_level and line.strip():
            explanation_lines.append(line.strip())

    return " ".join(explanation_lines) if explanation_lines else None


def _line_contains_level(line: str) -> bool:
    """Check if line contains a confidence level keyword."""
    line_upper = line.upper()
    return any(word in line_upper for word in ["HIGH", "MEDIUM", "LOW"])


def _extract_fallback_root_cause(response: str) -> str:
    """Extract root cause from unstructured response."""
    # If no proper section found, use first paragraph as root cause
    paragraphs = response.split("\n\n")
    for para in paragraphs:
        para = para.strip()
        if para and not para.startswith("#"):
            return para
    return response[:500] if response else "Unable to determine root cause"


def _extract_fallback_fix(response: str) -> str:
    """Extract fix suggestion from unstructured response."""
    # Look for common fix keywords
    fix_patterns = [
        r"try\s+(.+?)(?:\.|$)",
        r"suggest(?:ed)?\s+(?:fix|solution)?:?\s*(.+?)(?:\.|$)",
        r"recommend\s+(.+?)(?:\.|$)",
    ]

    for pattern in fix_patterns:
        match = re.search(pattern, response, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    return "Review the error details for suggested remediation."
