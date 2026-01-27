"""Tests for the validate_scenarios module (TDD)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

# --- Test Fixtures ---


@pytest.fixture
def fresh_metadata():
    """Metadata captured recently (within 30 days)."""
    captured_at = (datetime.now(UTC) - timedelta(days=5)).isoformat()
    return {
        "repo": "TryGhost/Ghost",
        "repo_url": "https://github.com/TryGhost/Ghost",
        "stars": 51700,
        "run_id": 21395156769,
        "run_url": "https://github.com/TryGhost/Ghost/actions/runs/21395156769",
        "captured_at": captured_at,
        "artifact_names": ["e2e-coverage"],
    }


@pytest.fixture
def stale_metadata():
    """Metadata captured long ago (> 90 days)."""
    captured_at = (datetime.now(UTC) - timedelta(days=100)).isoformat()
    return {
        "repo": "old/repo",
        "repo_url": "https://github.com/old/repo",
        "stars": 100,
        "run_id": 12345,
        "run_url": "https://github.com/old/repo/actions/runs/12345",
        "captured_at": captured_at,
        "artifact_names": ["playwright-report"],
    }


@pytest.fixture
def sample_diagnosis():
    """Sample diagnosis.json content."""
    return {
        "repo": "TryGhost/Ghost",
        "run_id": 21395156769,
        "diagnosis": {
            "root_cause": "Timeout waiting for selector",
            "evidence": ["Element not found"],
            "suggested_fix": "Add explicit wait",
            "confidence": "HIGH",
        },
        "analyzed_at": datetime.now(UTC).isoformat(),
    }


@pytest.fixture
def complete_scenario(tmp_path, fresh_metadata, sample_diagnosis):
    """Create a complete scenario with all required files."""
    scenario_dir = tmp_path / "complete-scenario-123"
    scenario_dir.mkdir()

    (scenario_dir / "metadata.json").write_text(json.dumps(fresh_metadata, indent=2))
    (scenario_dir / "report.json").write_text('{"suites": [], "stats": {}}')
    (scenario_dir / "diagnosis.json").write_text(json.dumps(sample_diagnosis, indent=2))

    return scenario_dir


@pytest.fixture
def incomplete_scenario(tmp_path, fresh_metadata):
    """Create scenario missing diagnosis.json."""
    scenario_dir = tmp_path / "incomplete-scenario-456"
    scenario_dir.mkdir()

    (scenario_dir / "metadata.json").write_text(json.dumps(fresh_metadata, indent=2))
    (scenario_dir / "report.json").write_text('{"suites": [], "stats": {}}')
    # No diagnosis.json

    return scenario_dir


@pytest.fixture
def stale_scenario(tmp_path, stale_metadata, sample_diagnosis):
    """Create a stale scenario (captured > 90 days ago)."""
    scenario_dir = tmp_path / "stale-scenario-789"
    scenario_dir.mkdir()

    (scenario_dir / "metadata.json").write_text(json.dumps(stale_metadata, indent=2))
    (scenario_dir / "report.json").write_text('{"suites": [], "stats": {}}')
    (scenario_dir / "diagnosis.json").write_text(json.dumps(sample_diagnosis, indent=2))

    return scenario_dir


@pytest.fixture
def scenarios_dir_mixed(tmp_path, fresh_metadata, stale_metadata, sample_diagnosis):
    """Create scenarios directory with mixed validity."""
    scenarios = tmp_path / "scenarios"
    scenarios.mkdir()

    # Valid scenario
    s1 = scenarios / "valid-123"
    s1.mkdir()
    (s1 / "metadata.json").write_text(json.dumps(fresh_metadata, indent=2))
    (s1 / "report.json").write_text('{"suites": [], "stats": {}}')
    (s1 / "diagnosis.json").write_text(json.dumps(sample_diagnosis, indent=2))

    # Stale scenario
    s2 = scenarios / "stale-456"
    s2.mkdir()
    (s2 / "metadata.json").write_text(json.dumps(stale_metadata, indent=2))
    (s2 / "report.json").write_text('{"suites": [], "stats": {}}')
    (s2 / "diagnosis.json").write_text(json.dumps(sample_diagnosis, indent=2))

    # Incomplete scenario (no diagnosis)
    s3 = scenarios / "incomplete-789"
    s3.mkdir()
    (s3 / "metadata.json").write_text(json.dumps(fresh_metadata, indent=2))
    (s3 / "report.json").write_text('{"suites": [], "stats": {}}')

    return scenarios


# --- ValidatorConfig Tests ---


class TestValidatorConfig:
    """Tests for ValidatorConfig dataclass."""

    def test_config_requires_scenarios_dir(self):
        """ValidatorConfig should require scenarios_dir."""
        from heisenberg.validate_scenarios import ValidatorConfig

        config = ValidatorConfig(scenarios_dir=Path("/tmp/scenarios"))
        assert config.scenarios_dir == Path("/tmp/scenarios")

    def test_config_has_default_max_age_days(self):
        """ValidatorConfig should default max_age_days to 90."""
        from heisenberg.validate_scenarios import ValidatorConfig

        config = ValidatorConfig(scenarios_dir=Path("/tmp/scenarios"))
        assert config.max_age_days == 90

    def test_config_accepts_custom_max_age(self):
        """ValidatorConfig should accept custom max_age_days."""
        from heisenberg.validate_scenarios import ValidatorConfig

        config = ValidatorConfig(scenarios_dir=Path("/tmp/scenarios"), max_age_days=30)
        assert config.max_age_days == 30

    def test_config_has_require_diagnosis_flag(self):
        """ValidatorConfig should have require_diagnosis flag."""
        from heisenberg.validate_scenarios import ValidatorConfig

        config = ValidatorConfig(scenarios_dir=Path("/tmp/scenarios"), require_diagnosis=True)
        assert config.require_diagnosis is True

    def test_config_require_diagnosis_defaults_true(self):
        """require_diagnosis should default to True."""
        from heisenberg.validate_scenarios import ValidatorConfig

        config = ValidatorConfig(scenarios_dir=Path("/tmp/scenarios"))
        assert config.require_diagnosis is True


# --- ValidationResult Tests ---


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_result_has_scenario_id(self):
        """ValidationResult should have scenario_id."""
        from heisenberg.validate_scenarios import ValidationResult, ValidationStatus

        result = ValidationResult(
            scenario_id="test-123",
            status=ValidationStatus.VALID,
            issues=[],
        )
        assert result.scenario_id == "test-123"

    def test_result_has_status(self):
        """ValidationResult should have status."""
        from heisenberg.validate_scenarios import ValidationResult, ValidationStatus

        result = ValidationResult(
            scenario_id="test-123",
            status=ValidationStatus.STALE,
            issues=["Too old"],
        )
        assert result.status == ValidationStatus.STALE

    def test_result_has_issues_list(self):
        """ValidationResult should have issues list."""
        from heisenberg.validate_scenarios import ValidationResult, ValidationStatus

        result = ValidationResult(
            scenario_id="test-123",
            status=ValidationStatus.INVALID,
            issues=["Missing metadata.json", "Missing report.json"],
        )
        assert len(result.issues) == 2

    def test_result_is_valid_property(self):
        """ValidationResult.is_valid should return True only for VALID status."""
        from heisenberg.validate_scenarios import ValidationResult, ValidationStatus

        valid = ValidationResult("a", ValidationStatus.VALID, [])
        stale = ValidationResult("b", ValidationStatus.STALE, ["old"])
        invalid = ValidationResult("c", ValidationStatus.INVALID, ["broken"])

        assert valid.is_valid is True
        assert stale.is_valid is False
        assert invalid.is_valid is False


# --- ScenarioValidator Tests ---


class TestScenarioValidator:
    """Tests for ScenarioValidator class."""

    def test_validator_requires_config(self, tmp_path):
        """ScenarioValidator should require config."""
        from heisenberg.validate_scenarios import ScenarioValidator, ValidatorConfig

        config = ValidatorConfig(scenarios_dir=tmp_path)
        validator = ScenarioValidator(config)
        assert validator.config == config

    def test_validate_scenario_returns_result(self, complete_scenario):
        """validate_scenario should return ValidationResult."""
        from heisenberg.validate_scenarios import (
            ScenarioValidator,
            ValidationResult,
            ValidatorConfig,
        )

        config = ValidatorConfig(scenarios_dir=complete_scenario.parent)
        validator = ScenarioValidator(config)

        result = validator.validate_scenario(complete_scenario)

        assert isinstance(result, ValidationResult)

    def test_complete_scenario_is_valid(self, complete_scenario):
        """Complete fresh scenario should be VALID."""
        from heisenberg.validate_scenarios import (
            ScenarioValidator,
            ValidationStatus,
            ValidatorConfig,
        )

        config = ValidatorConfig(scenarios_dir=complete_scenario.parent)
        validator = ScenarioValidator(config)

        result = validator.validate_scenario(complete_scenario)

        assert result.status == ValidationStatus.VALID
        assert result.issues == []

    def test_stale_scenario_is_stale(self, stale_scenario):
        """Scenario older than max_age_days should be STALE."""
        from heisenberg.validate_scenarios import (
            ScenarioValidator,
            ValidationStatus,
            ValidatorConfig,
        )

        config = ValidatorConfig(scenarios_dir=stale_scenario.parent, max_age_days=90)
        validator = ScenarioValidator(config)

        result = validator.validate_scenario(stale_scenario)

        assert result.status == ValidationStatus.STALE
        assert any("age" in issue.lower() or "old" in issue.lower() for issue in result.issues)

    def test_incomplete_scenario_is_invalid(self, incomplete_scenario):
        """Scenario missing diagnosis.json should be INVALID when require_diagnosis=True."""
        from heisenberg.validate_scenarios import (
            ScenarioValidator,
            ValidationStatus,
            ValidatorConfig,
        )

        config = ValidatorConfig(scenarios_dir=incomplete_scenario.parent, require_diagnosis=True)
        validator = ScenarioValidator(config)

        result = validator.validate_scenario(incomplete_scenario)

        assert result.status == ValidationStatus.INVALID
        assert any("diagnosis" in issue.lower() for issue in result.issues)

    def test_incomplete_scenario_valid_when_diagnosis_not_required(self, incomplete_scenario):
        """Scenario missing diagnosis should be VALID when require_diagnosis=False."""
        from heisenberg.validate_scenarios import (
            ScenarioValidator,
            ValidationStatus,
            ValidatorConfig,
        )

        config = ValidatorConfig(scenarios_dir=incomplete_scenario.parent, require_diagnosis=False)
        validator = ScenarioValidator(config)

        result = validator.validate_scenario(incomplete_scenario)

        assert result.status == ValidationStatus.VALID

    def test_missing_metadata_is_invalid(self, tmp_path):
        """Scenario missing metadata.json should be INVALID."""
        from heisenberg.validate_scenarios import (
            ScenarioValidator,
            ValidationStatus,
            ValidatorConfig,
        )

        scenario_dir = tmp_path / "no-metadata-123"
        scenario_dir.mkdir()
        (scenario_dir / "report.json").write_text("{}")

        config = ValidatorConfig(scenarios_dir=tmp_path)
        validator = ScenarioValidator(config)

        result = validator.validate_scenario(scenario_dir)

        assert result.status == ValidationStatus.INVALID
        assert any("metadata" in issue.lower() for issue in result.issues)

    def test_missing_report_is_invalid(self, tmp_path, fresh_metadata):
        """Scenario missing report.json should be INVALID."""
        from heisenberg.validate_scenarios import (
            ScenarioValidator,
            ValidationStatus,
            ValidatorConfig,
        )

        scenario_dir = tmp_path / "no-report-123"
        scenario_dir.mkdir()
        (scenario_dir / "metadata.json").write_text(json.dumps(fresh_metadata))

        config = ValidatorConfig(scenarios_dir=tmp_path, require_diagnosis=False)
        validator = ScenarioValidator(config)

        result = validator.validate_scenario(scenario_dir)

        assert result.status == ValidationStatus.INVALID
        assert any("report" in issue.lower() for issue in result.issues)


# --- Validate All Tests ---


class TestValidateAll:
    """Tests for validate_all method."""

    def test_validate_all_returns_list(self, scenarios_dir_mixed):
        """validate_all should return list of ValidationResults."""
        from heisenberg.validate_scenarios import ScenarioValidator, ValidatorConfig

        config = ValidatorConfig(scenarios_dir=scenarios_dir_mixed)
        validator = ScenarioValidator(config)

        results = validator.validate_all()

        assert isinstance(results, list)
        assert len(results) == 3  # valid, stale, incomplete

    def test_validate_all_checks_each_scenario(self, scenarios_dir_mixed):
        """validate_all should check each scenario directory."""
        from heisenberg.validate_scenarios import ScenarioValidator, ValidatorConfig

        config = ValidatorConfig(scenarios_dir=scenarios_dir_mixed)
        validator = ScenarioValidator(config)

        results = validator.validate_all()

        scenario_ids = {r.scenario_id for r in results}
        assert "valid-123" in scenario_ids
        assert "stale-456" in scenario_ids
        assert "incomplete-789" in scenario_ids

    def test_validate_all_empty_dir(self, tmp_path):
        """validate_all should return empty list for empty directory."""
        from heisenberg.validate_scenarios import ScenarioValidator, ValidatorConfig

        config = ValidatorConfig(scenarios_dir=tmp_path)
        validator = ScenarioValidator(config)

        results = validator.validate_all()

        assert results == []


# --- ValidationReport Tests ---


class TestValidationReport:
    """Tests for ValidationReport."""

    def test_generate_report_returns_report(self, scenarios_dir_mixed):
        """generate_report should return ValidationReport."""
        from heisenberg.validate_scenarios import (
            ScenarioValidator,
            ValidationReport,
            ValidatorConfig,
        )

        config = ValidatorConfig(scenarios_dir=scenarios_dir_mixed)
        validator = ScenarioValidator(config)

        report = validator.generate_report()

        assert isinstance(report, ValidationReport)

    def test_report_has_summary_stats(self, scenarios_dir_mixed):
        """ValidationReport should have summary statistics."""
        from heisenberg.validate_scenarios import ScenarioValidator, ValidatorConfig

        config = ValidatorConfig(scenarios_dir=scenarios_dir_mixed)
        validator = ScenarioValidator(config)

        report = validator.generate_report()

        assert report.total == 3
        assert report.valid >= 0
        assert report.stale >= 0
        assert report.invalid >= 0
        assert report.valid + report.stale + report.invalid == report.total

    def test_report_has_results_list(self, scenarios_dir_mixed):
        """ValidationReport should contain individual results."""
        from heisenberg.validate_scenarios import ScenarioValidator, ValidatorConfig

        config = ValidatorConfig(scenarios_dir=scenarios_dir_mixed)
        validator = ScenarioValidator(config)

        report = validator.generate_report()

        assert len(report.results) == 3

    def test_report_to_dict(self, scenarios_dir_mixed):
        """ValidationReport should serialize to dict."""
        from heisenberg.validate_scenarios import ScenarioValidator, ValidatorConfig

        config = ValidatorConfig(scenarios_dir=scenarios_dir_mixed)
        validator = ScenarioValidator(config)

        report = validator.generate_report()
        data = report.to_dict()

        assert "summary" in data
        assert "results" in data
        assert data["summary"]["total"] == 3

    def test_report_to_json(self, scenarios_dir_mixed):
        """ValidationReport should serialize to JSON."""
        from heisenberg.validate_scenarios import ScenarioValidator, ValidatorConfig

        config = ValidatorConfig(scenarios_dir=scenarios_dir_mixed)
        validator = ScenarioValidator(config)

        report = validator.generate_report()
        json_str = report.to_json()

        # Should be valid JSON
        parsed = json.loads(json_str)
        assert "summary" in parsed


# --- Edge Cases ---


class TestValidationEdgeCases:
    """Tests for edge cases in validation."""

    def test_invalid_json_in_metadata(self, tmp_path):
        """Invalid JSON in metadata.json should result in INVALID."""
        from heisenberg.validate_scenarios import (
            ScenarioValidator,
            ValidationStatus,
            ValidatorConfig,
        )

        scenario_dir = tmp_path / "bad-json-123"
        scenario_dir.mkdir()
        (scenario_dir / "metadata.json").write_text("not valid json {{{")
        (scenario_dir / "report.json").write_text("{}")

        config = ValidatorConfig(scenarios_dir=tmp_path, require_diagnosis=False)
        validator = ScenarioValidator(config)

        result = validator.validate_scenario(scenario_dir)

        assert result.status == ValidationStatus.INVALID
        assert any("json" in issue.lower() or "parse" in issue.lower() for issue in result.issues)

    def test_missing_captured_at_in_metadata(self, tmp_path):
        """Missing captured_at in metadata should result in INVALID."""
        from heisenberg.validate_scenarios import (
            ScenarioValidator,
            ValidationStatus,
            ValidatorConfig,
        )

        scenario_dir = tmp_path / "no-date-123"
        scenario_dir.mkdir()
        metadata = {"repo": "test/repo", "run_id": 123}  # No captured_at
        (scenario_dir / "metadata.json").write_text(json.dumps(metadata))
        (scenario_dir / "report.json").write_text("{}")

        config = ValidatorConfig(scenarios_dir=tmp_path, require_diagnosis=False)
        validator = ScenarioValidator(config)

        result = validator.validate_scenario(scenario_dir)

        assert result.status == ValidationStatus.INVALID
        assert any("captured_at" in issue.lower() for issue in result.issues)

    def test_custom_max_age_threshold(self, tmp_path):
        """Custom max_age_days should affect staleness check."""
        from heisenberg.validate_scenarios import (
            ScenarioValidator,
            ValidationStatus,
            ValidatorConfig,
        )

        # Scenario captured 40 days ago
        captured_at = (datetime.now(UTC) - timedelta(days=40)).isoformat()
        metadata = {
            "repo": "test/repo",
            "run_id": 123,
            "captured_at": captured_at,
        }

        scenario_dir = tmp_path / "medium-age-123"
        scenario_dir.mkdir()
        (scenario_dir / "metadata.json").write_text(json.dumps(metadata))
        (scenario_dir / "report.json").write_text("{}")

        # With 90-day threshold, should be valid
        config_90 = ValidatorConfig(
            scenarios_dir=tmp_path, max_age_days=90, require_diagnosis=False
        )
        validator_90 = ScenarioValidator(config_90)
        result_90 = validator_90.validate_scenario(scenario_dir)
        assert result_90.status == ValidationStatus.VALID

        # With 30-day threshold, should be stale
        config_30 = ValidatorConfig(
            scenarios_dir=tmp_path, max_age_days=30, require_diagnosis=False
        )
        validator_30 = ScenarioValidator(config_30)
        result_30 = validator_30.validate_scenario(scenario_dir)
        assert result_30.status == ValidationStatus.STALE
