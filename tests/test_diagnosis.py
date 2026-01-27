"""Tests for diagnosis parser - TDD Red-Green-Refactor."""

import pytest

from heisenberg.core.diagnosis import (
    ConfidenceLevel,
    Diagnosis,
    _determine_confidence_level,
    _extract_confidence_explanation,
    _extract_evidence,
    _extract_fallback_fix,
    _extract_fallback_root_cause,
    _extract_section,
    _line_contains_level,
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


class TestExtractSection:
    """Test suite for _extract_section helper function."""

    def test_extracts_section_between_headers(self):
        """Should extract content between two markdown headers."""
        response = """## Root Cause Analysis
This is the root cause content.

## Evidence
This is evidence."""

        result = _extract_section(response, "Root Cause Analysis", "Evidence")

        assert result == "This is the root cause content."

    def test_returns_empty_for_missing_header(self):
        """Should return empty string if header not found."""
        response = "No headers here, just plain text."

        result = _extract_section(response, "Root Cause Analysis", "Evidence")

        assert result == ""

    def test_extracts_until_end_if_no_end_header(self):
        """Should extract until end if end header not found."""
        response = """## Root Cause Analysis
Content goes until end of text."""

        result = _extract_section(response, "Root Cause Analysis", "NonExistent")

        assert "Content goes until end" in result

    def test_header_matching_is_case_insensitive(self):
        """Should match headers case-insensitively."""
        response = """## root cause analysis
Lower case header content.

## evidence
More content."""

        result = _extract_section(response, "Root Cause Analysis", "Evidence")

        assert result == "Lower case header content."


class TestExtractEvidence:
    """Test suite for _extract_evidence helper function."""

    def test_extracts_bullet_points_with_dash(self):
        """Should extract bullet points starting with dash."""
        response = """## Evidence
- First evidence item
- Second evidence item

## Suggested Fix
Fix here."""

        result = _extract_evidence(response)

        assert len(result) == 2
        assert "First evidence item" in result
        assert "Second evidence item" in result

    def test_extracts_bullet_points_with_asterisk(self):
        """Should extract bullet points starting with asterisk."""
        response = """## Evidence
* Item one
* Item two

## Suggested Fix
Fix."""

        result = _extract_evidence(response)

        assert len(result) == 2
        assert "Item one" in result

    def test_returns_empty_list_for_no_evidence_section(self):
        """Should return empty list if no Evidence section."""
        response = "No evidence section here."

        result = _extract_evidence(response)

        assert result == []

    def test_ignores_non_bullet_lines(self):
        """Should ignore lines not starting with bullet markers."""
        response = """## Evidence
- Valid bullet
Plain line should be ignored
- Another valid bullet

## Suggested Fix
Fix."""

        result = _extract_evidence(response)

        assert len(result) == 2
        assert "Plain line" not in str(result)


class TestLineContainsLevel:
    """Test suite for _line_contains_level helper function."""

    def test_detects_high(self):
        """Should detect HIGH in line."""
        assert _line_contains_level("HIGH (>80%)") is True

    def test_detects_medium(self):
        """Should detect MEDIUM in line."""
        assert _line_contains_level("MEDIUM confidence") is True

    def test_detects_low(self):
        """Should detect LOW in line."""
        assert _line_contains_level("LOW - not enough data") is True

    def test_case_insensitive(self):
        """Should detect levels case-insensitively."""
        assert _line_contains_level("high confidence") is True
        assert _line_contains_level("Medium level") is True
        assert _line_contains_level("low") is True

    def test_returns_false_for_no_level(self):
        """Should return False if no level keyword found."""
        assert _line_contains_level("Some other text") is False
        assert _line_contains_level("") is False


class TestDetermineConfidenceLevel:
    """Test suite for _determine_confidence_level helper function."""

    def test_returns_high_for_high_text(self):
        """Should return HIGH for text containing HIGH."""
        assert _determine_confidence_level("HIGH (>80%)") == ConfidenceLevel.HIGH

    def test_returns_medium_for_medium_text(self):
        """Should return MEDIUM for text containing MEDIUM."""
        assert _determine_confidence_level("MEDIUM confidence") == ConfidenceLevel.MEDIUM

    def test_returns_low_for_low_text(self):
        """Should return LOW for text containing LOW."""
        assert _determine_confidence_level("LOW - uncertain") == ConfidenceLevel.LOW

    def test_returns_unknown_for_no_match(self):
        """Should return UNKNOWN if no level keyword found."""
        assert _determine_confidence_level("uncertain") == ConfidenceLevel.UNKNOWN

    def test_high_takes_precedence(self):
        """HIGH should be detected first if multiple levels present."""
        # HIGH appears first in the mapping, so it wins
        assert _determine_confidence_level("HIGH and MEDIUM") == ConfidenceLevel.HIGH


class TestExtractConfidenceExplanation:
    """Test suite for _extract_confidence_explanation helper function."""

    def test_extracts_text_after_level_line(self):
        """Should extract explanation after the confidence level line."""
        text = """HIGH (>80%)
This is the explanation text.
More explanation here."""

        result = _extract_confidence_explanation(text)

        assert result is not None
        assert "explanation text" in result
        assert "More explanation" in result

    def test_returns_none_for_no_explanation(self):
        """Should return None if no text after level line."""
        text = "HIGH (>80%)"

        result = _extract_confidence_explanation(text)

        assert result is None

    def test_ignores_text_before_level_line(self):
        """Should only include text after the level line."""
        text = """Preamble text here
HIGH
Actual explanation."""

        result = _extract_confidence_explanation(text)

        assert result is not None
        assert "Actual explanation" in result
        assert "Preamble" not in result

    def test_handles_multiline_explanation(self):
        """Should join multiple explanation lines."""
        text = """MEDIUM
First line.
Second line.
Third line."""

        result = _extract_confidence_explanation(text)

        assert "First line" in result
        assert "Second line" in result
        assert "Third line" in result


class TestExtractFallbackRootCause:
    """Test suite for _extract_fallback_root_cause helper function."""

    def test_extracts_first_paragraph(self):
        """Should extract first non-header paragraph."""
        response = """This is the first paragraph with the root cause.

This is the second paragraph."""

        result = _extract_fallback_root_cause(response)

        assert "first paragraph" in result

    def test_skips_header_lines(self):
        """Should skip paragraphs starting with #."""
        response = """# Header line

This is actual content."""

        result = _extract_fallback_root_cause(response)

        assert result == "This is actual content."

    def test_truncates_long_response(self):
        """Should truncate response to 500 chars if all paragraphs are headers."""
        # All paragraphs start with #, so fallback to truncation
        long_text = "# " + "x" * 1000

        result = _extract_fallback_root_cause(long_text)

        assert len(result) == 500

    def test_returns_default_for_empty_response(self):
        """Should return default message for empty response."""
        result = _extract_fallback_root_cause("")

        assert result == "Unable to determine root cause"


class TestExtractFallbackFix:
    """Test suite for _extract_fallback_fix helper function."""

    def test_extracts_try_suggestion(self):
        """Should extract suggestion starting with 'try'."""
        response = "You should try increasing the timeout."

        result = _extract_fallback_fix(response)

        assert "increasing the timeout" in result

    def test_extracts_suggest_pattern(self):
        """Should extract 'suggest' pattern."""
        response = "I suggest using a different selector."

        result = _extract_fallback_fix(response)

        assert "using a different selector" in result

    def test_extracts_recommend_pattern(self):
        """Should extract 'recommend' pattern."""
        response = "I recommend checking the logs"

        result = _extract_fallback_fix(response)

        assert "checking the logs" in result

    def test_returns_default_for_no_pattern(self):
        """Should return default message if no pattern matches."""
        response = "No clear fix suggestion here."

        result = _extract_fallback_fix(response)

        assert result == "Review the error details for suggested remediation."


class TestParseDiagnosisEdgeCases:
    """Additional edge case tests for parse_diagnosis to kill mutants."""

    def test_suggested_fix_extracted_not_none(self):
        """Verify suggested_fix is actually extracted, not defaulted to None."""
        response = """## Root Cause Analysis
Issue found.

## Evidence
- Some evidence

## Suggested Fix
Specific fix that must be extracted.

## Confidence
HIGH"""

        diagnosis = parse_diagnosis(response)

        # This kills mutant that sets suggested_fix = None
        assert diagnosis.suggested_fix == "Specific fix that must be extracted."

    def test_root_cause_extracted_not_fallback(self):
        """Verify root_cause is extracted from section, not fallback."""
        response = """## Root Cause Analysis
Extracted root cause here.

## Evidence
- Evidence item

## Suggested Fix
Fix.

## Confidence
MEDIUM"""

        diagnosis = parse_diagnosis(response)

        # This kills mutant that changes header to "XXRoot Cause AnalysisXX"
        assert diagnosis.root_cause == "Extracted root cause here."

    def test_evidence_section_header_exact(self):
        """Verify Evidence section uses correct header."""
        response = """## Root Cause Analysis
Cause.

## Evidence
- Must extract this evidence

## Suggested Fix
Fix.

## Confidence
LOW"""

        diagnosis = parse_diagnosis(response)

        # This kills mutant that changes "Evidence" to "XXEvidenceXX"
        assert len(diagnosis.evidence) == 1
        assert "Must extract this evidence" in diagnosis.evidence[0]

    def test_confidence_explanation_requires_found_level_false_initially(self):
        """Test that explanation extraction depends on finding level line first."""
        # If found_level started as True, this would incorrectly include the first line
        text = """Not a level line
HIGH (>80%)
This is the real explanation."""

        result = _extract_confidence_explanation(text)

        # Should only get text after HIGH line, not "Not a level line"
        assert result is not None
        assert "real explanation" in result
        assert "Not a level" not in result

    def test_diagnosis_confidence_explanation_default_is_none(self):
        """Verify confidence_explanation defaults to None, not empty string."""
        diagnosis = Diagnosis(
            root_cause="cause",
            evidence=[],
            suggested_fix="fix",
            confidence=ConfidenceLevel.HIGH,
            raw_response="response",
        )

        # This kills mutant that changes default from None to ""
        assert diagnosis.confidence_explanation is None
