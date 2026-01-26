"""Tests for diagnosis parser - TDD Red-Green-Refactor."""

import pytest

from heisenberg.diagnosis import (
    ConfidenceLevel,
    Diagnosis,
    parse_diagnosis,
)


class TestConfidenceLevel:
    """Test suite for confidence level enum."""

    @pytest.mark.parametrize(
        "level,expected_value",
        [
            (ConfidenceLevel.HIGH, "HIGH"),
            (ConfidenceLevel.MEDIUM, "MEDIUM"),
            (ConfidenceLevel.LOW, "LOW"),
            (ConfidenceLevel.UNKNOWN, "UNKNOWN"),
        ],
    )
    def test_confidence_level_values(self, level, expected_value):
        """Confidence level enum should have correct string values."""
        assert level.value == expected_value


class TestDiagnosis:
    """Test suite for Diagnosis data model."""

    def test_diagnosis_has_root_cause(self):
        """Diagnosis should contain root cause."""
        # When
        diagnosis = Diagnosis(
            root_cause="Database timeout",
            evidence=["Log shows connection failed"],
            suggested_fix="Increase timeout",
            confidence=ConfidenceLevel.HIGH,
            confidence_explanation="Clear evidence in logs",
            raw_response="Full response",
        )

        # Then
        assert diagnosis.root_cause == "Database timeout"

    def test_diagnosis_has_evidence(self):
        """Diagnosis should contain evidence list."""
        # When
        diagnosis = Diagnosis(
            root_cause="Timeout",
            evidence=["Error 1", "Error 2"],
            suggested_fix="Fix",
            confidence=ConfidenceLevel.MEDIUM,
            raw_response="Response",
        )

        # Then
        assert len(diagnosis.evidence) == 2
        assert "Error 1" in diagnosis.evidence

    def test_diagnosis_has_suggested_fix(self):
        """Diagnosis should contain suggested fix."""
        # When
        diagnosis = Diagnosis(
            root_cause="Bug",
            evidence=[],
            suggested_fix="Add retry logic",
            confidence=ConfidenceLevel.HIGH,
            raw_response="Response",
        )

        # Then
        assert diagnosis.suggested_fix == "Add retry logic"

    def test_diagnosis_has_confidence(self):
        """Diagnosis should have confidence level."""
        # When
        diagnosis = Diagnosis(
            root_cause="Issue",
            evidence=[],
            suggested_fix="Fix",
            confidence=ConfidenceLevel.LOW,
            raw_response="Response",
        )

        # Then
        assert diagnosis.confidence == ConfidenceLevel.LOW

    def test_diagnosis_preserves_raw_response(self):
        """Diagnosis should preserve raw LLM response."""
        # When
        diagnosis = Diagnosis(
            root_cause="Issue",
            evidence=[],
            suggested_fix="Fix",
            confidence=ConfidenceLevel.MEDIUM,
            raw_response="## Root Cause\nFull text here",
        )

        # Then
        assert "Root Cause" in diagnosis.raw_response


class TestParseDiagnosis:
    """Test suite for diagnosis parsing from LLM response."""

    def test_parses_root_cause(self):
        """Should extract root cause from response."""
        # Given
        response = """## Root Cause Analysis
The test failure is caused by a database connection timeout. The backend API failed to respond within the expected time.

## Evidence
- Error message shows "TimeoutError: 30000ms exceeded"
- Backend logs show "Connection pool exhausted"

## Suggested Fix
Increase the database connection pool size or add retry logic.

## Confidence Score
HIGH (>80%)
Clear correlation between backend logs and test failure."""

        # When
        diagnosis = parse_diagnosis(response)

        # Then
        assert "database connection timeout" in diagnosis.root_cause.lower()

    def test_parses_evidence(self):
        """Should extract evidence items from response."""
        # Given
        response = """## Root Cause Analysis
Network latency issue.

## Evidence
- Error message indicates timeout
- Network logs show high latency
- API response time exceeded 5s

## Suggested Fix
Optimize API endpoint.

## Confidence Score
MEDIUM (50-80%)"""

        # When
        diagnosis = parse_diagnosis(response)

        # Then
        assert len(diagnosis.evidence) >= 2
        assert any("timeout" in e.lower() for e in diagnosis.evidence)

    def test_parses_suggested_fix(self):
        """Should extract suggested fix from response."""
        # Given
        response = """## Root Cause Analysis
Flaky selector.

## Evidence
- Element not found error

## Suggested Fix
Use data-testid attribute instead of CSS selector. This provides more stable element identification.

## Confidence Score
HIGH"""

        # When
        diagnosis = parse_diagnosis(response)

        # Then
        assert "data-testid" in diagnosis.suggested_fix.lower()

    @pytest.mark.parametrize(
        "confidence_text,expected_level",
        [
            ("HIGH (>80%)\nVery clear evidence.", ConfidenceLevel.HIGH),
            ("MEDIUM (50-80%)\nSome evidence but not conclusive.", ConfidenceLevel.MEDIUM),
            ("LOW (<50%)\nNot enough information to determine root cause.", ConfidenceLevel.LOW),
        ],
    )
    def test_parses_confidence_level(self, confidence_text, expected_level):
        """Should parse confidence level from response."""
        # Given
        response = f"""## Root Cause Analysis
Test issue.

## Evidence
- Some evidence

## Suggested Fix
Fix it.

## Confidence Score
{confidence_text}"""

        # When
        diagnosis = parse_diagnosis(response)

        # Then
        assert diagnosis.confidence == expected_level

    def test_handles_missing_sections_gracefully(self):
        """Should handle responses without all sections."""
        # Given
        response = """The test failed due to a timeout.

The backend was slow to respond. Try increasing the timeout."""

        # When
        diagnosis = parse_diagnosis(response)

        # Then
        assert diagnosis.confidence == ConfidenceLevel.UNKNOWN
        assert "timeout" in diagnosis.raw_response.lower()

    def test_preserves_raw_response(self):
        """Should preserve full raw response."""
        # Given
        response = "Full LLM response text here with all details."

        # When
        diagnosis = parse_diagnosis(response)

        # Then
        assert diagnosis.raw_response == response

    def test_extracts_confidence_explanation(self):
        """Should extract confidence explanation."""
        # Given
        response = """## Root Cause Analysis
Bug found.

## Evidence
- Clear evidence

## Suggested Fix
Fix it.

## Confidence Score
HIGH (>80%)
The stack trace clearly shows the error location and the backend logs confirm the issue."""

        # When
        diagnosis = parse_diagnosis(response)

        # Then
        assert diagnosis.confidence_explanation is not None
        assert "stack trace" in diagnosis.confidence_explanation.lower()
