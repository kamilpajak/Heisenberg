"""Tests for the validate-cases CLI command."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from heisenberg.cli.commands import run_validate_cases

if TYPE_CHECKING:
    pass


# --- Fixtures ---


@pytest.fixture
def valid_scenario(tmp_path: Path) -> Path:
    """Create a valid scenario directory."""
    case_dir = tmp_path / "test-scenario-123"
    case_dir.mkdir()

    metadata = {
        "repo": "owner/repo",
        "run_id": 123,
        "captured_at": "2026-01-27T12:00:00Z",
    }
    (case_dir / "metadata.json").write_text(json.dumps(metadata))
    (case_dir / "report.json").write_text("{}")

    return case_dir


@pytest.fixture
def stale_scenario(tmp_path: Path) -> Path:
    """Create a stale scenario directory (older than 90 days)."""
    case_dir = tmp_path / "stale-scenario-456"
    case_dir.mkdir()

    metadata = {
        "repo": "owner/repo",
        "run_id": 456,
        "captured_at": "2025-01-01T12:00:00Z",  # Very old
    }
    (case_dir / "metadata.json").write_text(json.dumps(metadata))
    (case_dir / "report.json").write_text("{}")

    return case_dir


@pytest.fixture
def invalid_scenario(tmp_path: Path) -> Path:
    """Create an invalid scenario directory (missing report)."""
    case_dir = tmp_path / "invalid-scenario-789"
    case_dir.mkdir()

    metadata = {
        "repo": "owner/repo",
        "run_id": 789,
        "captured_at": "2026-01-27T12:00:00Z",
    }
    (case_dir / "metadata.json").write_text(json.dumps(metadata))
    # No report.json

    return case_dir


# --- Directory Not Found Tests ---


class TestDirectoryNotFound:
    """Tests for non-existent directory handling."""

    def test_returns_error_for_missing_dir(self, tmp_path: Path) -> None:
        """Should return 1 for non-existent directory."""
        args = argparse.Namespace(
            cases_dir=tmp_path / "nonexistent",
            max_age=90,
            no_require_diagnosis=True,
            json=False,
        )

        result = run_validate_cases(args)

        assert result == 1

    def test_prints_error_for_missing_dir(self, tmp_path: Path, capsys) -> None:
        """Should print error message for non-existent directory."""
        missing_dir = tmp_path / "nonexistent"
        args = argparse.Namespace(
            cases_dir=missing_dir,
            max_age=90,
            no_require_diagnosis=True,
            json=False,
        )

        run_validate_cases(args)

        captured = capsys.readouterr()
        assert "not found" in captured.err.lower()
        assert str(missing_dir) in captured.err


# --- Text Output Tests ---


class TestTextOutput:
    """Tests for human-readable text output."""

    def test_prints_report_header(self, valid_scenario: Path, capsys) -> None:
        """Should print report header with directory path."""
        args = argparse.Namespace(
            cases_dir=valid_scenario.parent,
            max_age=90,
            no_require_diagnosis=True,
            json=False,
        )

        run_validate_cases(args)

        captured = capsys.readouterr()
        assert "Validation Report for:" in captured.out
        assert str(valid_scenario.parent) in captured.out

    def test_prints_summary_stats(self, valid_scenario: Path, capsys) -> None:
        """Should print summary statistics."""
        args = argparse.Namespace(
            cases_dir=valid_scenario.parent,
            max_age=90,
            no_require_diagnosis=True,
            json=False,
        )

        run_validate_cases(args)

        captured = capsys.readouterr()
        assert "Total:" in captured.out
        assert "Valid:" in captured.out
        assert "Stale:" in captured.out
        assert "Invalid:" in captured.out

    def test_prints_issues_when_stale(self, stale_scenario: Path, capsys) -> None:
        """Should print issues section for stale cases."""
        args = argparse.Namespace(
            cases_dir=stale_scenario.parent,
            max_age=90,
            no_require_diagnosis=True,
            json=False,
        )

        run_validate_cases(args)

        captured = capsys.readouterr()
        assert "Issues found:" in captured.out
        assert "STALE" in captured.out

    def test_prints_issues_when_invalid(self, invalid_scenario: Path, capsys) -> None:
        """Should print issues section for invalid cases."""
        args = argparse.Namespace(
            cases_dir=invalid_scenario.parent,
            max_age=90,
            no_require_diagnosis=True,
            json=False,
        )

        run_validate_cases(args)

        captured = capsys.readouterr()
        assert "Issues found:" in captured.out
        assert "INVALID" in captured.out

    def test_prints_issue_details(self, invalid_scenario: Path, capsys) -> None:
        """Should print detailed issue messages."""
        args = argparse.Namespace(
            cases_dir=invalid_scenario.parent,
            max_age=90,
            no_require_diagnosis=True,
            json=False,
        )

        run_validate_cases(args)

        captured = capsys.readouterr()
        # Should show issue detail like "Missing report.json"
        assert "report" in captured.out.lower()


# --- JSON Output Tests ---


class TestJsonOutput:
    """Tests for JSON output format."""

    def test_json_flag_outputs_json(self, valid_scenario: Path, capsys) -> None:
        """Should output valid JSON when --json flag is set."""
        args = argparse.Namespace(
            cases_dir=valid_scenario.parent,
            max_age=90,
            no_require_diagnosis=True,
            json=True,
        )

        run_validate_cases(args)

        captured = capsys.readouterr()
        # Should be valid JSON
        data = json.loads(captured.out)
        assert "summary" in data
        assert "total" in data["summary"]
        assert "valid" in data["summary"]


# --- Return Code Tests ---


class TestReturnCodes:
    """Tests for return code behavior."""

    def test_returns_zero_for_valid_scenarios(self, valid_scenario: Path) -> None:
        """Should return 0 when all scenarios are valid."""
        args = argparse.Namespace(
            cases_dir=valid_scenario.parent,
            max_age=90,
            no_require_diagnosis=True,
            json=False,
        )

        result = run_validate_cases(args)

        assert result == 0

    def test_returns_one_for_stale_scenarios(self, stale_scenario: Path) -> None:
        """Should return 1 when scenarios are stale."""
        args = argparse.Namespace(
            cases_dir=stale_scenario.parent,
            max_age=90,
            no_require_diagnosis=True,
            json=False,
        )

        result = run_validate_cases(args)

        assert result == 1

    def test_returns_one_for_invalid_scenarios(self, invalid_scenario: Path) -> None:
        """Should return 1 when scenarios are invalid."""
        args = argparse.Namespace(
            cases_dir=invalid_scenario.parent,
            max_age=90,
            no_require_diagnosis=True,
            json=False,
        )

        result = run_validate_cases(args)

        assert result == 1


# --- Error Handling Tests ---


class TestErrorHandling:
    """Tests for error handling."""

    def test_handles_validator_exception(self, tmp_path: Path, capsys) -> None:
        """Should return 1 and print error on validator exception."""
        args = argparse.Namespace(
            cases_dir=tmp_path,
            max_age=90,
            no_require_diagnosis=True,
            json=False,
        )

        with patch("heisenberg.cli.commands.CaseValidator") as MockValidator:
            instance = MagicMock()
            instance.generate_report.side_effect = ValueError("Test error")
            MockValidator.return_value = instance

            result = run_validate_cases(args)

            assert result == 1
            captured = capsys.readouterr()
            assert "Test error" in captured.err
