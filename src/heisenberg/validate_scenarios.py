"""Validate frozen scenarios for freshness and completeness.

This module checks if frozen scenarios are still valid for the demo,
flagging stale or incomplete entries.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any


class ValidationStatus(Enum):
    """Status of scenario validation."""

    VALID = "valid"
    STALE = "stale"
    INVALID = "invalid"


@dataclass
class ValidatorConfig:
    """Configuration for scenario validation."""

    scenarios_dir: Path
    max_age_days: int = 90  # GitHub artifacts expire after 90 days
    require_diagnosis: bool = True


@dataclass
class ValidationResult:
    """Result of validating a single scenario."""

    scenario_id: str
    status: ValidationStatus
    issues: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Check if scenario passed validation."""
        return self.status == ValidationStatus.VALID

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "scenario_id": self.scenario_id,
            "status": self.status.value,
            "is_valid": self.is_valid,
            "issues": self.issues,
        }


@dataclass
class ValidationReport:
    """Report summarizing validation of all scenarios."""

    results: list[ValidationResult]
    validated_at: str

    @property
    def total(self) -> int:
        """Total number of scenarios validated."""
        return len(self.results)

    @property
    def valid(self) -> int:
        """Number of valid scenarios."""
        return sum(1 for r in self.results if r.status == ValidationStatus.VALID)

    @property
    def stale(self) -> int:
        """Number of stale scenarios."""
        return sum(1 for r in self.results if r.status == ValidationStatus.STALE)

    @property
    def invalid(self) -> int:
        """Number of invalid scenarios."""
        return sum(1 for r in self.results if r.status == ValidationStatus.INVALID)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "validated_at": self.validated_at,
            "summary": {
                "total": self.total,
                "valid": self.valid,
                "stale": self.stale,
                "invalid": self.invalid,
            },
            "results": [r.to_dict() for r in self.results],
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


class ScenarioValidator:
    """Validates frozen scenarios for freshness and completeness."""

    def __init__(self, config: ValidatorConfig):
        """Initialize validator with configuration.

        Args:
            config: ValidatorConfig with scenarios_dir and validation settings.
        """
        self.config = config

    def validate_scenario(self, scenario_dir: Path) -> ValidationResult:
        """Validate a single scenario directory.

        Args:
            scenario_dir: Path to scenario directory.

        Returns:
            ValidationResult with status and any issues found.
        """
        scenario_id = scenario_dir.name
        issues: list[str] = []

        # Check for required files
        metadata_path = scenario_dir / "metadata.json"
        report_path = scenario_dir / "report.json"
        diagnosis_path = scenario_dir / "diagnosis.json"

        if not metadata_path.exists():
            issues.append("Missing metadata.json")
            return ValidationResult(scenario_id, ValidationStatus.INVALID, issues)

        if not report_path.exists():
            issues.append("Missing report.json")
            return ValidationResult(scenario_id, ValidationStatus.INVALID, issues)

        # Load and validate metadata
        try:
            metadata = json.loads(metadata_path.read_text())
        except json.JSONDecodeError as e:
            issues.append(f"Invalid JSON in metadata.json: {e}")
            return ValidationResult(scenario_id, ValidationStatus.INVALID, issues)

        # Check for captured_at
        captured_at_str = metadata.get("captured_at")
        if not captured_at_str:
            issues.append("Missing captured_at in metadata")
            return ValidationResult(scenario_id, ValidationStatus.INVALID, issues)

        # Check age
        try:
            # Parse ISO format timestamp
            if captured_at_str.endswith("Z"):
                captured_at_str = captured_at_str[:-1] + "+00:00"
            captured_at = datetime.fromisoformat(captured_at_str)
            age_days = (datetime.now(UTC) - captured_at).days

            if age_days > self.config.max_age_days:
                issues.append(f"Scenario is {age_days} days old (max: {self.config.max_age_days})")
                return ValidationResult(scenario_id, ValidationStatus.STALE, issues)
        except ValueError as e:
            issues.append(f"Invalid captured_at format: {e}")
            return ValidationResult(scenario_id, ValidationStatus.INVALID, issues)

        # Check for diagnosis if required
        if self.config.require_diagnosis and not diagnosis_path.exists():
            issues.append("Missing diagnosis.json (analysis not completed)")
            return ValidationResult(scenario_id, ValidationStatus.INVALID, issues)

        return ValidationResult(scenario_id, ValidationStatus.VALID, issues)

    def validate_all(self) -> list[ValidationResult]:
        """Validate all scenarios in the scenarios directory.

        Returns:
            List of ValidationResults for each scenario.
        """
        if not self.config.scenarios_dir.exists():
            return []

        results = []
        for scenario_dir in sorted(self.config.scenarios_dir.iterdir()):
            if scenario_dir.is_dir():
                result = self.validate_scenario(scenario_dir)
                results.append(result)

        return results

    def generate_report(self) -> ValidationReport:
        """Generate a validation report for all scenarios.

        Returns:
            ValidationReport with summary and individual results.
        """
        results = self.validate_all()
        validated_at = datetime.now(UTC).isoformat()

        return ValidationReport(
            results=results,
            validated_at=validated_at,
        )
