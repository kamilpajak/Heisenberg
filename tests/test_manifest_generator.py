"""Tests for the manifest_generator module (TDD)."""

from __future__ import annotations

import json
from pathlib import Path

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
def sample_diagnosis():
    """Sample diagnosis.json content."""
    return {
        "repo": "TryGhost/Ghost",
        "run_id": 21395156769,
        "diagnosis": {
            "root_cause": "Timeout waiting for login button selector due to slow network",
            "evidence": ["Element not found within 30s", "Network request pending"],
            "suggested_fix": "Add explicit wait or check selector",
            "confidence": "HIGH",
            "confidence_explanation": "Clear timeout error with stack trace",
        },
        "tokens": {"input": 1500, "output": 500, "total": 2000},
        "provider": "anthropic",
        "model": "claude-sonnet-4-20250514",
        "analyzed_at": "2026-01-27T14:00:00Z",
    }


@pytest.fixture
def sample_diagnosis_medium():
    """Sample diagnosis with MEDIUM confidence."""
    return {
        "repo": "formkit/auto-animate",
        "run_id": 12345,
        "diagnosis": {
            "root_cause": "Animation timing issue",
            "evidence": ["Flaky behavior observed"],
            "suggested_fix": "Increase animation timeout",
            "confidence": "MEDIUM",
            "confidence_explanation": "Some uncertainty in root cause",
        },
        "tokens": {"input": 1000, "output": 400, "total": 1400},
        "provider": "anthropic",
        "model": None,
        "analyzed_at": "2026-01-27T15:00:00Z",
    }


@pytest.fixture
def sample_diagnosis_low():
    """Sample diagnosis with LOW confidence."""
    return {
        "repo": "evcc-io/evcc",
        "run_id": 99999,
        "diagnosis": {
            "root_cause": "Unknown intermittent failure",
            "evidence": [],
            "suggested_fix": "Investigate further",
            "confidence": "LOW",
            "confidence_explanation": "Cannot determine root cause",
        },
        "tokens": {"input": 800, "output": 300, "total": 1100},
        "provider": "anthropic",
        "model": None,
        "analyzed_at": "2026-01-27T16:00:00Z",
    }


@pytest.fixture
def case_dir_with_diagnosis(tmp_path, sample_metadata, sample_diagnosis):
    """Create a case directory with metadata and diagnosis."""
    case_dir = tmp_path / "tryghost-ghost-21395156769"
    case_dir.mkdir()

    (case_dir / "metadata.json").write_text(json.dumps(sample_metadata, indent=2))
    (case_dir / "diagnosis.json").write_text(json.dumps(sample_diagnosis, indent=2))
    (case_dir / "report.json").write_text("{}")

    return case_dir


@pytest.fixture
def case_dir_without_diagnosis(tmp_path, sample_metadata):
    """Create a case directory with metadata but no diagnosis."""
    case_dir = tmp_path / "pending-case-12345"
    case_dir.mkdir()

    (case_dir / "metadata.json").write_text(json.dumps(sample_metadata, indent=2))
    (case_dir / "report.json").write_text("{}")

    return case_dir


@pytest.fixture
def cases_dir_multiple(tmp_path, sample_metadata, sample_diagnosis, sample_diagnosis_medium):
    """Create cases directory with multiple cases."""
    cases = tmp_path / "cases"
    cases.mkdir()

    # Case 1 - HIGH confidence
    s1 = cases / "tryghost-ghost-21395156769"
    s1.mkdir()
    (s1 / "metadata.json").write_text(json.dumps(sample_metadata, indent=2))
    (s1 / "diagnosis.json").write_text(json.dumps(sample_diagnosis, indent=2))
    (s1 / "report.json").write_text("{}")

    # Case 2 - MEDIUM confidence
    s2_meta = {**sample_metadata, "repo": "formkit/auto-animate", "run_id": 12345}
    s2 = cases / "formkit-auto-animate-12345"
    s2.mkdir()
    (s2 / "metadata.json").write_text(json.dumps(s2_meta, indent=2))
    (s2 / "diagnosis.json").write_text(json.dumps(sample_diagnosis_medium, indent=2))
    (s2 / "report.json").write_text("{}")

    return cases


# --- GeneratorConfig Tests ---


class TestGeneratorConfig:
    """Tests for GeneratorConfig dataclass."""

    def test_config_requires_cases_dir(self):
        """GeneratorConfig should require cases_dir."""
        from heisenberg.playground.manifest import GeneratorConfig

        config = GeneratorConfig(cases_dir=Path("/tmp/cases"))
        assert config.cases_dir == Path("/tmp/cases")

    def test_config_has_default_output_path(self):
        """GeneratorConfig should default output to manifest.json in cases_dir."""
        from heisenberg.playground.manifest import GeneratorConfig

        config = GeneratorConfig(cases_dir=Path("/tmp/cases"))
        assert config.output_path == Path("/tmp/cases/manifest.json")

    def test_config_accepts_custom_output_path(self):
        """GeneratorConfig should accept custom output path."""
        from heisenberg.playground.manifest import GeneratorConfig

        config = GeneratorConfig(
            cases_dir=Path("/tmp/cases"),
            output_path=Path("/tmp/custom/manifest.json"),
        )
        assert config.output_path == Path("/tmp/custom/manifest.json")

    def test_config_has_include_pending_flag(self):
        """GeneratorConfig should have include_pending flag."""
        from heisenberg.playground.manifest import GeneratorConfig

        config = GeneratorConfig(cases_dir=Path("/tmp/cases"), include_pending=True)
        assert config.include_pending is True

    def test_config_include_pending_defaults_false(self):
        """include_pending should default to False."""
        from heisenberg.playground.manifest import GeneratorConfig

        config = GeneratorConfig(cases_dir=Path("/tmp/cases"))
        assert config.include_pending is False


# --- ManifestGenerator Tests ---


class TestManifestGenerator:
    """Tests for ManifestGenerator class."""

    def test_generator_requires_config(self, tmp_path):
        """ManifestGenerator should require config."""
        from heisenberg.playground.manifest import GeneratorConfig, ManifestGenerator

        config = GeneratorConfig(cases_dir=tmp_path)
        generator = ManifestGenerator(config)
        assert generator.config == config

    def test_discover_cases_finds_directories(self, cases_dir_multiple):
        """discover_cases should find all case directories."""
        from heisenberg.playground.manifest import GeneratorConfig, ManifestGenerator

        config = GeneratorConfig(cases_dir=cases_dir_multiple)
        generator = ManifestGenerator(config)

        cases = generator.discover_cases()

        assert len(cases) == 2
        case_ids = {s.name for s in cases}
        assert "tryghost-ghost-21395156769" in case_ids
        assert "formkit-auto-animate-12345" in case_ids

    def test_discover_cases_ignores_files(self, tmp_path):
        """discover_cases should ignore files, only return directories."""
        from heisenberg.playground.manifest import GeneratorConfig, ManifestGenerator

        (tmp_path / "readme.md").write_text("# README")
        (tmp_path / "case-123").mkdir()

        config = GeneratorConfig(cases_dir=tmp_path)
        generator = ManifestGenerator(config)

        cases = generator.discover_cases()

        assert len(cases) == 1
        assert cases[0].name == "case-123"

    def test_discover_cases_empty_dir(self, tmp_path):
        """discover_cases should return empty list for empty directory."""
        from heisenberg.playground.manifest import GeneratorConfig, ManifestGenerator

        config = GeneratorConfig(cases_dir=tmp_path)
        generator = ManifestGenerator(config)

        cases = generator.discover_cases()

        assert cases == []


class TestLoadCaseData:
    """Tests for loading case data."""

    def test_load_case_returns_entry(self, case_dir_with_diagnosis):
        """load_case should return CaseEntry."""
        from heisenberg.playground.manifest import CaseEntry, GeneratorConfig, ManifestGenerator

        config = GeneratorConfig(cases_dir=case_dir_with_diagnosis.parent)
        generator = ManifestGenerator(config)

        entry = generator.load_case(case_dir_with_diagnosis)

        assert isinstance(entry, CaseEntry)

    def test_load_case_extracts_id(self, case_dir_with_diagnosis):
        """load_case should extract case ID from directory name."""
        from heisenberg.playground.manifest import GeneratorConfig, ManifestGenerator

        config = GeneratorConfig(cases_dir=case_dir_with_diagnosis.parent)
        generator = ManifestGenerator(config)

        entry = generator.load_case(case_dir_with_diagnosis)

        assert entry.id == "tryghost-ghost-21395156769"

    def test_load_case_extracts_source_info(self, case_dir_with_diagnosis):
        """load_case should extract source info from metadata."""
        from heisenberg.playground.manifest import GeneratorConfig, ManifestGenerator

        config = GeneratorConfig(cases_dir=case_dir_with_diagnosis.parent)
        generator = ManifestGenerator(config)

        entry = generator.load_case(case_dir_with_diagnosis)

        assert entry.source["repo"] == "TryGhost/Ghost"
        assert entry.source["stars"] == 51700
        assert entry.source["original_run_id"] == 21395156769

    def test_load_case_extracts_validation_from_diagnosis(self, case_dir_with_diagnosis):
        """load_case should extract validation info from diagnosis."""
        from heisenberg.playground.manifest import GeneratorConfig, ManifestGenerator

        config = GeneratorConfig(cases_dir=case_dir_with_diagnosis.parent)
        generator = ManifestGenerator(config)

        entry = generator.load_case(case_dir_with_diagnosis)

        assert entry.validation["confidence"] == "HIGH"
        assert "root_cause" in entry.validation

    def test_load_case_builds_asset_paths(self, case_dir_with_diagnosis):
        """load_case should build relative asset paths."""
        from heisenberg.playground.manifest import GeneratorConfig, ManifestGenerator

        config = GeneratorConfig(cases_dir=case_dir_with_diagnosis.parent)
        generator = ManifestGenerator(config)

        entry = generator.load_case(case_dir_with_diagnosis)

        assert entry.assets["report"] == "tryghost-ghost-21395156769/report.json"
        assert entry.assets["diagnosis"] == "tryghost-ghost-21395156769/diagnosis.json"

    def test_load_case_without_diagnosis_returns_pending(self, case_dir_without_diagnosis):
        """load_case without diagnosis should mark as pending."""
        from heisenberg.playground.manifest import GeneratorConfig, ManifestGenerator

        config = GeneratorConfig(cases_dir=case_dir_without_diagnosis.parent)
        generator = ManifestGenerator(config)

        entry = generator.load_case(case_dir_without_diagnosis)

        assert entry.validation["status"] == "pending"
        assert entry.assets.get("diagnosis") is None


# --- Manifest Generation Tests ---


class TestGenerateManifest:
    """Tests for generate() method."""

    def test_generate_returns_manifest(self, cases_dir_multiple):
        """generate() should return Manifest object."""
        from heisenberg.playground.manifest import GeneratorConfig, Manifest, ManifestGenerator

        config = GeneratorConfig(cases_dir=cases_dir_multiple)
        generator = ManifestGenerator(config)

        manifest = generator.generate()

        assert isinstance(manifest, Manifest)

    def test_generate_includes_all_analyzed_cases(self, cases_dir_multiple):
        """generate() should include all cases with diagnosis."""
        from heisenberg.playground.manifest import GeneratorConfig, ManifestGenerator

        config = GeneratorConfig(cases_dir=cases_dir_multiple)
        generator = ManifestGenerator(config)

        manifest = generator.generate()

        assert len(manifest.cases) == 2

    def test_generate_excludes_pending_by_default(
        self, tmp_path, sample_metadata, sample_diagnosis
    ):
        """generate() should exclude pending cases by default."""
        from heisenberg.playground.manifest import GeneratorConfig, ManifestGenerator

        # Create one analyzed and one pending
        s1 = tmp_path / "analyzed-123"
        s1.mkdir()
        (s1 / "metadata.json").write_text(json.dumps(sample_metadata))
        (s1 / "diagnosis.json").write_text(json.dumps(sample_diagnosis))
        (s1 / "report.json").write_text("{}")

        s2 = tmp_path / "pending-456"
        s2.mkdir()
        (s2 / "metadata.json").write_text(json.dumps(sample_metadata))
        (s2 / "report.json").write_text("{}")

        config = GeneratorConfig(cases_dir=tmp_path)
        generator = ManifestGenerator(config)

        manifest = generator.generate()

        assert len(manifest.cases) == 1
        assert manifest.cases[0].id == "analyzed-123"

    def test_generate_includes_pending_when_flag_set(
        self, tmp_path, sample_metadata, sample_diagnosis
    ):
        """generate() should include pending cases when include_pending=True."""
        from heisenberg.playground.manifest import GeneratorConfig, ManifestGenerator

        s1 = tmp_path / "analyzed-123"
        s1.mkdir()
        (s1 / "metadata.json").write_text(json.dumps(sample_metadata))
        (s1 / "diagnosis.json").write_text(json.dumps(sample_diagnosis))
        (s1 / "report.json").write_text("{}")

        s2 = tmp_path / "pending-456"
        s2.mkdir()
        (s2 / "metadata.json").write_text(json.dumps(sample_metadata))
        (s2 / "report.json").write_text("{}")

        config = GeneratorConfig(cases_dir=tmp_path, include_pending=True)
        generator = ManifestGenerator(config)

        manifest = generator.generate()

        assert len(manifest.cases) == 2

    def test_generate_sets_generated_at(self, cases_dir_multiple):
        """generate() should set generated_at timestamp."""
        from heisenberg.playground.manifest import GeneratorConfig, ManifestGenerator

        config = GeneratorConfig(cases_dir=cases_dir_multiple)
        generator = ManifestGenerator(config)

        manifest = generator.generate()

        assert manifest.generated_at is not None
        # Should be ISO format
        assert "T" in manifest.generated_at


# --- Stats Calculation Tests ---


class TestCalculateStats:
    """Tests for stats calculation."""

    def test_stats_counts_total_cases(self, cases_dir_multiple):
        """Stats should count total cases."""
        from heisenberg.playground.manifest import GeneratorConfig, ManifestGenerator

        config = GeneratorConfig(cases_dir=cases_dir_multiple)
        generator = ManifestGenerator(config)

        manifest = generator.generate()

        assert manifest.stats["total_cases"] == 2

    def test_stats_counts_by_confidence(
        self,
        tmp_path,
        sample_metadata,
        sample_diagnosis,
        sample_diagnosis_medium,
        sample_diagnosis_low,
    ):
        """Stats should count cases by confidence level."""
        from heisenberg.playground.manifest import GeneratorConfig, ManifestGenerator

        # HIGH
        s1 = tmp_path / "high-123"
        s1.mkdir()
        (s1 / "metadata.json").write_text(json.dumps(sample_metadata))
        (s1 / "diagnosis.json").write_text(json.dumps(sample_diagnosis))
        (s1 / "report.json").write_text("{}")

        # MEDIUM
        s2 = tmp_path / "medium-456"
        s2.mkdir()
        (s2 / "metadata.json").write_text(json.dumps({**sample_metadata, "run_id": 456}))
        (s2 / "diagnosis.json").write_text(json.dumps(sample_diagnosis_medium))
        (s2 / "report.json").write_text("{}")

        # LOW
        s3 = tmp_path / "low-789"
        s3.mkdir()
        (s3 / "metadata.json").write_text(json.dumps({**sample_metadata, "run_id": 789}))
        (s3 / "diagnosis.json").write_text(json.dumps(sample_diagnosis_low))
        (s3 / "report.json").write_text("{}")

        config = GeneratorConfig(cases_dir=tmp_path)
        generator = ManifestGenerator(config)

        manifest = generator.generate()

        assert manifest.stats["high_confidence"] == 1
        assert manifest.stats["medium_confidence"] == 1
        assert manifest.stats["low_confidence"] == 1


# --- Manifest Serialization Tests ---


class TestManifestSerialization:
    """Tests for Manifest serialization."""

    def test_manifest_to_dict(self, cases_dir_multiple):
        """Manifest should serialize to dict."""
        from heisenberg.playground.manifest import GeneratorConfig, ManifestGenerator

        config = GeneratorConfig(cases_dir=cases_dir_multiple)
        generator = ManifestGenerator(config)

        manifest = generator.generate()
        data = manifest.to_dict()

        assert "generated_at" in data
        assert "cases" in data
        assert "stats" in data
        assert isinstance(data["cases"], list)

    def test_manifest_to_json(self, cases_dir_multiple):
        """Manifest should serialize to JSON string."""
        from heisenberg.playground.manifest import GeneratorConfig, ManifestGenerator

        config = GeneratorConfig(cases_dir=cases_dir_multiple)
        generator = ManifestGenerator(config)

        manifest = generator.generate()
        json_str = manifest.to_json()

        # Should be valid JSON
        parsed = json.loads(json_str)
        assert "cases" in parsed


# --- Save Manifest Tests ---


class TestSaveManifest:
    """Tests for saving manifest to file."""

    def test_save_writes_manifest_file(self, cases_dir_multiple):
        """save() should write manifest.json to output path."""
        from heisenberg.playground.manifest import GeneratorConfig, ManifestGenerator

        output_path = cases_dir_multiple / "manifest.json"
        config = GeneratorConfig(cases_dir=cases_dir_multiple, output_path=output_path)
        generator = ManifestGenerator(config)

        manifest = generator.generate()
        generator.save(manifest)

        assert output_path.exists()

    def test_saved_manifest_is_valid_json(self, cases_dir_multiple):
        """Saved manifest.json should be valid JSON."""
        from heisenberg.playground.manifest import GeneratorConfig, ManifestGenerator

        output_path = cases_dir_multiple / "manifest.json"
        config = GeneratorConfig(cases_dir=cases_dir_multiple, output_path=output_path)
        generator = ManifestGenerator(config)

        manifest = generator.generate()
        generator.save(manifest)

        data = json.loads(output_path.read_text())
        assert "cases" in data
        assert "stats" in data

    def test_generate_and_save_convenience(self, cases_dir_multiple):
        """generate_and_save() should generate and save in one call."""
        from heisenberg.playground.manifest import GeneratorConfig, ManifestGenerator

        output_path = cases_dir_multiple / "manifest.json"
        config = GeneratorConfig(cases_dir=cases_dir_multiple, output_path=output_path)
        generator = ManifestGenerator(config)

        manifest = generator.generate_and_save()

        assert output_path.exists()
        assert manifest.stats["total_cases"] == 2
