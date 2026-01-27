"""Tests for the analyze_scenario module (TDD)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

# --- Test Fixtures ---


@pytest.fixture
def sample_metadata():
    """Sample metadata.json content."""
    return {
        "repo": "TryGhost/Ghost",
        "repo_url": "https://github.com/TryGhost/Ghost",
        "stars": 51700,
        "run_id": 21395156769,
        "run_url": "https://github.com/TryGhost/Ghost/actions/runs/21395156769",
        "captured_at": "2026-01-27T12:00:00Z",
        "artifact_names": ["e2e-coverage"],
    }


@pytest.fixture
def sample_report():
    """Sample Playwright report.json content."""
    return {
        "config": {
            "rootDir": "/app",
            "timeout": 30000,
        },
        "suites": [
            {
                "title": "Login tests",
                "file": "tests/login.spec.ts",
                "specs": [
                    {
                        "title": "should login successfully",
                        "ok": False,
                        "tests": [
                            {
                                "expectedStatus": "passed",
                                "status": "failed",
                                "results": [
                                    {
                                        "status": "failed",
                                        "duration": 5000,
                                        "error": {
                                            "message": "Timeout waiting for selector",
                                            "stack": "Error: Timeout\n    at login.spec.ts:15",
                                        },
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
        "stats": {
            "expected": 1,
            "unexpected": 1,
            "flaky": 0,
            "skipped": 0,
        },
    }


@pytest.fixture
def frozen_scenario(tmp_path, sample_metadata, sample_report):
    """Create a frozen scenario directory with metadata and report."""
    scenario_dir = tmp_path / "tryghost-ghost-21395156769"
    scenario_dir.mkdir()

    metadata_path = scenario_dir / "metadata.json"
    metadata_path.write_text(json.dumps(sample_metadata, indent=2))

    report_path = scenario_dir / "report.json"
    report_path.write_text(json.dumps(sample_report, indent=2))

    return scenario_dir


@pytest.fixture
def mock_diagnosis():
    """Create a mock Diagnosis object."""
    from heisenberg.diagnosis import ConfidenceLevel, Diagnosis

    return Diagnosis(
        root_cause="Timeout waiting for login button selector",
        evidence=["Element not found within 30s", "Network request pending"],
        suggested_fix="Add explicit wait or check selector",
        confidence=ConfidenceLevel.HIGH,
        confidence_explanation="Clear timeout error with stack trace",
        raw_response="## Root Cause Analysis\n...",
    )


@pytest.fixture
def mock_ai_result(mock_diagnosis):
    """Create a mock AIAnalysisResult."""
    from heisenberg.ai_analyzer import AIAnalysisResult

    return AIAnalysisResult(
        diagnosis=mock_diagnosis,
        input_tokens=1500,
        output_tokens=500,
        provider="anthropic",
        model="claude-sonnet-4-20250514",
    )


# --- Config Tests ---


class TestAnalyzeConfig:
    """Tests for AnalyzeConfig dataclass."""

    def test_config_requires_scenario_dir(self):
        """AnalyzeConfig should require scenario_dir."""
        from heisenberg.analyze_scenario import AnalyzeConfig

        config = AnalyzeConfig(scenario_dir=Path("/tmp/scenario"))
        assert config.scenario_dir == Path("/tmp/scenario")

    def test_config_has_default_provider(self):
        """AnalyzeConfig should default to anthropic provider."""
        from heisenberg.analyze_scenario import AnalyzeConfig

        config = AnalyzeConfig(scenario_dir=Path("/tmp/scenario"))
        assert config.provider == "anthropic"

    def test_config_accepts_custom_provider(self):
        """AnalyzeConfig should accept custom provider."""
        from heisenberg.analyze_scenario import AnalyzeConfig

        config = AnalyzeConfig(scenario_dir=Path("/tmp/scenario"), provider="openai")
        assert config.provider == "openai"

    def test_config_accepts_model(self):
        """AnalyzeConfig should accept model parameter."""
        from heisenberg.analyze_scenario import AnalyzeConfig

        config = AnalyzeConfig(
            scenario_dir=Path("/tmp/scenario"),
            model="claude-opus-4-20250514",
        )
        assert config.model == "claude-opus-4-20250514"

    def test_config_model_defaults_to_none(self):
        """Model should default to None (use provider default)."""
        from heisenberg.analyze_scenario import AnalyzeConfig

        config = AnalyzeConfig(scenario_dir=Path("/tmp/scenario"))
        assert config.model is None

    def test_config_accepts_api_key(self):
        """AnalyzeConfig should accept api_key parameter."""
        from heisenberg.analyze_scenario import AnalyzeConfig

        config = AnalyzeConfig(
            scenario_dir=Path("/tmp/scenario"),
            api_key="sk-test-key",
        )
        assert config.api_key == "sk-test-key"


# --- ScenarioAnalyzer Tests ---


class TestScenarioAnalyzer:
    """Tests for ScenarioAnalyzer class."""

    def test_analyzer_requires_config(self, frozen_scenario):
        """ScenarioAnalyzer should require config."""
        from heisenberg.analyze_scenario import AnalyzeConfig, ScenarioAnalyzer

        config = AnalyzeConfig(scenario_dir=frozen_scenario)
        analyzer = ScenarioAnalyzer(config)
        assert analyzer.config == config

    def test_analyzer_loads_metadata(self, frozen_scenario, sample_metadata):
        """ScenarioAnalyzer should load metadata from scenario directory."""
        from heisenberg.analyze_scenario import AnalyzeConfig, ScenarioAnalyzer

        config = AnalyzeConfig(scenario_dir=frozen_scenario)
        analyzer = ScenarioAnalyzer(config)

        metadata = analyzer.load_metadata()
        assert metadata["repo"] == sample_metadata["repo"]
        assert metadata["stars"] == sample_metadata["stars"]

    def test_analyzer_loads_report(self, frozen_scenario):
        """ScenarioAnalyzer should load report from scenario directory."""
        from heisenberg.analyze_scenario import AnalyzeConfig, ScenarioAnalyzer

        config = AnalyzeConfig(scenario_dir=frozen_scenario)
        analyzer = ScenarioAnalyzer(config)

        report = analyzer.load_report()
        assert "suites" in report
        assert "stats" in report

    def test_analyzer_raises_on_missing_metadata(self, tmp_path):
        """ScenarioAnalyzer should raise if metadata.json missing."""
        from heisenberg.analyze_scenario import AnalyzeConfig, ScenarioAnalyzer

        scenario_dir = tmp_path / "empty-scenario"
        scenario_dir.mkdir()

        config = AnalyzeConfig(scenario_dir=scenario_dir)
        analyzer = ScenarioAnalyzer(config)

        with pytest.raises(FileNotFoundError, match="metadata.json"):
            analyzer.load_metadata()

    def test_analyzer_raises_on_missing_report(self, tmp_path, sample_metadata):
        """ScenarioAnalyzer should raise if report.json missing."""
        from heisenberg.analyze_scenario import AnalyzeConfig, ScenarioAnalyzer

        scenario_dir = tmp_path / "no-report-scenario"
        scenario_dir.mkdir()
        (scenario_dir / "metadata.json").write_text(json.dumps(sample_metadata))

        config = AnalyzeConfig(scenario_dir=scenario_dir)
        analyzer = ScenarioAnalyzer(config)

        with pytest.raises(FileNotFoundError, match="report.json"):
            analyzer.load_report()


class TestScenarioAnalyzerAnalyze:
    """Tests for ScenarioAnalyzer.analyze() method."""

    def test_analyze_returns_analysis_result(self, frozen_scenario, mock_ai_result):
        """analyze() should return AnalysisResult."""
        from heisenberg.analyze_scenario import AnalysisResult, AnalyzeConfig, ScenarioAnalyzer

        config = AnalyzeConfig(scenario_dir=frozen_scenario)
        analyzer = ScenarioAnalyzer(config)

        with patch("heisenberg.analyze_scenario.AIAnalyzer") as MockAI:
            MockAI.return_value.analyze.return_value = mock_ai_result

            result = analyzer.analyze()

            assert isinstance(result, AnalysisResult)

    def test_analyze_creates_ai_analyzer_with_report(self, frozen_scenario, mock_ai_result):
        """analyze() should create AIAnalyzer with parsed PlaywrightReport."""
        from heisenberg.analyze_scenario import AnalyzeConfig, ScenarioAnalyzer

        config = AnalyzeConfig(scenario_dir=frozen_scenario)
        analyzer = ScenarioAnalyzer(config)

        with patch("heisenberg.analyze_scenario.AIAnalyzer") as MockAI:
            MockAI.return_value.analyze.return_value = mock_ai_result

            analyzer.analyze()

            # Check AIAnalyzer was called with a PlaywrightReport
            call_kwargs = MockAI.call_args.kwargs
            assert "report" in call_kwargs
            # Report should be a PlaywrightReport, not raw dict
            from heisenberg.playwright_parser import PlaywrightReport

            assert isinstance(call_kwargs["report"], PlaywrightReport)

    def test_analyze_uses_config_provider(self, frozen_scenario, mock_ai_result):
        """analyze() should use provider from config."""
        from heisenberg.analyze_scenario import AnalyzeConfig, ScenarioAnalyzer

        config = AnalyzeConfig(scenario_dir=frozen_scenario, provider="openai")
        analyzer = ScenarioAnalyzer(config)

        with patch("heisenberg.analyze_scenario.AIAnalyzer") as MockAI:
            MockAI.return_value.analyze.return_value = mock_ai_result

            analyzer.analyze()

            call_kwargs = MockAI.call_args.kwargs
            assert call_kwargs["provider"] == "openai"

    def test_analyze_uses_config_model(self, frozen_scenario, mock_ai_result):
        """analyze() should use model from config."""
        from heisenberg.analyze_scenario import AnalyzeConfig, ScenarioAnalyzer

        config = AnalyzeConfig(
            scenario_dir=frozen_scenario,
            model="gpt-5-turbo",
        )
        analyzer = ScenarioAnalyzer(config)

        with patch("heisenberg.analyze_scenario.AIAnalyzer") as MockAI:
            MockAI.return_value.analyze.return_value = mock_ai_result

            analyzer.analyze()

            call_kwargs = MockAI.call_args.kwargs
            assert call_kwargs["model"] == "gpt-5-turbo"

    def test_analyze_result_contains_diagnosis(
        self, frozen_scenario, mock_ai_result, mock_diagnosis
    ):
        """AnalysisResult should contain diagnosis details."""
        from heisenberg.analyze_scenario import AnalyzeConfig, ScenarioAnalyzer

        config = AnalyzeConfig(scenario_dir=frozen_scenario)
        analyzer = ScenarioAnalyzer(config)

        with patch("heisenberg.analyze_scenario.AIAnalyzer") as MockAI:
            MockAI.return_value.analyze.return_value = mock_ai_result

            result = analyzer.analyze()

            assert result.root_cause == mock_diagnosis.root_cause
            assert result.evidence == mock_diagnosis.evidence
            assert result.suggested_fix == mock_diagnosis.suggested_fix
            assert result.confidence == mock_diagnosis.confidence.value

    def test_analyze_result_contains_metadata(
        self, frozen_scenario, mock_ai_result, sample_metadata
    ):
        """AnalysisResult should contain scenario metadata."""
        from heisenberg.analyze_scenario import AnalyzeConfig, ScenarioAnalyzer

        config = AnalyzeConfig(scenario_dir=frozen_scenario)
        analyzer = ScenarioAnalyzer(config)

        with patch("heisenberg.analyze_scenario.AIAnalyzer") as MockAI:
            MockAI.return_value.analyze.return_value = mock_ai_result

            result = analyzer.analyze()

            assert result.repo == sample_metadata["repo"]
            assert result.run_id == sample_metadata["run_id"]


# --- AnalysisResult Tests ---


class TestAnalysisResult:
    """Tests for AnalysisResult dataclass."""

    def test_analysis_result_to_dict(self, mock_diagnosis):
        """AnalysisResult should convert to dict for JSON serialization."""
        from heisenberg.analyze_scenario import AnalysisResult

        result = AnalysisResult(
            repo="owner/repo",
            run_id=12345,
            root_cause="Test failure",
            evidence=["Evidence 1", "Evidence 2"],
            suggested_fix="Fix it",
            confidence="HIGH",
            confidence_explanation="Clear error",
            input_tokens=1000,
            output_tokens=500,
            provider="anthropic",
            model="claude-sonnet-4-20250514",
        )

        data = result.to_dict()

        assert data["repo"] == "owner/repo"
        assert data["run_id"] == 12345
        assert data["diagnosis"]["root_cause"] == "Test failure"
        assert data["diagnosis"]["evidence"] == ["Evidence 1", "Evidence 2"]
        assert data["diagnosis"]["confidence"] == "HIGH"
        assert data["tokens"]["input"] == 1000
        assert data["tokens"]["output"] == 500

    def test_analysis_result_to_json(self, mock_diagnosis):
        """AnalysisResult should serialize to JSON."""
        from heisenberg.analyze_scenario import AnalysisResult

        result = AnalysisResult(
            repo="owner/repo",
            run_id=12345,
            root_cause="Test failure",
            evidence=["Evidence 1"],
            suggested_fix="Fix it",
            confidence="HIGH",
            confidence_explanation=None,
            input_tokens=1000,
            output_tokens=500,
            provider="anthropic",
            model=None,
        )

        json_str = result.to_json()
        parsed = json.loads(json_str)

        assert parsed["repo"] == "owner/repo"
        assert parsed["diagnosis"]["root_cause"] == "Test failure"


# --- Save Diagnosis Tests ---


class TestSaveDiagnosis:
    """Tests for saving diagnosis to file."""

    def test_analyzer_saves_diagnosis(self, frozen_scenario, mock_ai_result):
        """analyze() should save diagnosis.json to scenario directory."""
        from heisenberg.analyze_scenario import AnalyzeConfig, ScenarioAnalyzer

        config = AnalyzeConfig(scenario_dir=frozen_scenario)
        analyzer = ScenarioAnalyzer(config)

        with patch("heisenberg.analyze_scenario.AIAnalyzer") as MockAI:
            MockAI.return_value.analyze.return_value = mock_ai_result

            analyzer.analyze()

            diagnosis_path = frozen_scenario / "diagnosis.json"
            assert diagnosis_path.exists()

    def test_saved_diagnosis_is_valid_json(self, frozen_scenario, mock_ai_result):
        """Saved diagnosis.json should be valid JSON."""
        from heisenberg.analyze_scenario import AnalyzeConfig, ScenarioAnalyzer

        config = AnalyzeConfig(scenario_dir=frozen_scenario)
        analyzer = ScenarioAnalyzer(config)

        with patch("heisenberg.analyze_scenario.AIAnalyzer") as MockAI:
            MockAI.return_value.analyze.return_value = mock_ai_result

            analyzer.analyze()

            diagnosis_path = frozen_scenario / "diagnosis.json"
            data = json.loads(diagnosis_path.read_text())

            assert "diagnosis" in data
            assert "repo" in data

    def test_saved_diagnosis_contains_analyzed_at(self, frozen_scenario, mock_ai_result):
        """Saved diagnosis should include analyzed_at timestamp."""
        from heisenberg.analyze_scenario import AnalyzeConfig, ScenarioAnalyzer

        config = AnalyzeConfig(scenario_dir=frozen_scenario)
        analyzer = ScenarioAnalyzer(config)

        with patch("heisenberg.analyze_scenario.AIAnalyzer") as MockAI:
            MockAI.return_value.analyze.return_value = mock_ai_result

            analyzer.analyze()

            diagnosis_path = frozen_scenario / "diagnosis.json"
            data = json.loads(diagnosis_path.read_text())

            assert "analyzed_at" in data
            # Should be ISO format
            assert "T" in data["analyzed_at"]


# --- Error Handling Tests ---


class TestAnalyzeErrorHandling:
    """Tests for error handling in analyze()."""

    def test_analyze_raises_on_invalid_report(self, tmp_path, sample_metadata):
        """analyze() should raise on invalid report.json content."""
        from heisenberg.analyze_scenario import AnalyzeConfig, ScenarioAnalyzer

        scenario_dir = tmp_path / "bad-report-scenario"
        scenario_dir.mkdir()
        (scenario_dir / "metadata.json").write_text(json.dumps(sample_metadata))
        (scenario_dir / "report.json").write_text("not valid json")

        config = AnalyzeConfig(scenario_dir=scenario_dir)
        analyzer = ScenarioAnalyzer(config)

        with pytest.raises((json.JSONDecodeError, ValueError)):
            analyzer.analyze()

    def test_analyze_raises_on_ai_error(self, frozen_scenario):
        """analyze() should propagate AI analysis errors."""
        from heisenberg.analyze_scenario import AnalyzeConfig, ScenarioAnalyzer

        config = AnalyzeConfig(scenario_dir=frozen_scenario)
        analyzer = ScenarioAnalyzer(config)

        with patch("heisenberg.analyze_scenario.AIAnalyzer") as MockAI:
            MockAI.return_value.analyze.side_effect = ValueError("API key not set")

            with pytest.raises(ValueError, match="API key"):
                analyzer.analyze()
