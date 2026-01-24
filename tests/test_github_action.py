"""Tests for GitHub Action - TDD for reusable Heisenberg action."""

from pathlib import Path

import yaml

# Project root
PROJECT_ROOT = Path(__file__).parent.parent
ACTION_DIR = PROJECT_ROOT / "action"


class TestActionMetadata:
    """Test action.yml metadata file."""

    def test_action_yml_exists(self):
        """action.yml should exist in action directory."""
        action_file = ACTION_DIR / "action.yml"
        assert action_file.exists(), "action/action.yml not found"

    def test_action_yml_is_valid_yaml(self):
        """action.yml should be valid YAML."""
        action_file = ACTION_DIR / "action.yml"
        content = yaml.safe_load(action_file.read_text())
        assert content is not None

    def test_action_has_name(self):
        """action.yml should have a name."""
        action_file = ACTION_DIR / "action.yml"
        content = yaml.safe_load(action_file.read_text())
        assert "name" in content
        assert len(content["name"]) > 0

    def test_action_has_description(self):
        """action.yml should have a description."""
        action_file = ACTION_DIR / "action.yml"
        content = yaml.safe_load(action_file.read_text())
        assert "description" in content
        assert len(content["description"]) > 0

    def test_action_has_author(self):
        """action.yml should have an author."""
        action_file = ACTION_DIR / "action.yml"
        content = yaml.safe_load(action_file.read_text())
        assert "author" in content


class TestActionBranding:
    """Test action branding configuration."""

    def test_action_has_branding(self):
        """action.yml should have branding section."""
        action_file = ACTION_DIR / "action.yml"
        content = yaml.safe_load(action_file.read_text())
        assert "branding" in content

    def test_branding_has_icon(self):
        """Branding should have an icon."""
        action_file = ACTION_DIR / "action.yml"
        content = yaml.safe_load(action_file.read_text())
        assert "icon" in content.get("branding", {})

    def test_branding_has_color(self):
        """Branding should have a color."""
        action_file = ACTION_DIR / "action.yml"
        content = yaml.safe_load(action_file.read_text())
        assert "color" in content.get("branding", {})


class TestActionInputs:
    """Test action inputs configuration."""

    def test_action_has_inputs(self):
        """action.yml should have inputs section."""
        action_file = ACTION_DIR / "action.yml"
        content = yaml.safe_load(action_file.read_text())
        assert "inputs" in content

    def test_has_report_path_input(self):
        """Action should have report-path input."""
        action_file = ACTION_DIR / "action.yml"
        content = yaml.safe_load(action_file.read_text())
        inputs = content.get("inputs", {})
        assert "report-path" in inputs

    def test_report_path_is_required(self):
        """report-path input should be required."""
        action_file = ACTION_DIR / "action.yml"
        content = yaml.safe_load(action_file.read_text())
        report_path = content.get("inputs", {}).get("report-path", {})
        assert report_path.get("required") is True

    def test_has_api_key_input(self):
        """Action should have api-key input."""
        action_file = ACTION_DIR / "action.yml"
        content = yaml.safe_load(action_file.read_text())
        inputs = content.get("inputs", {})
        assert "api-key" in inputs

    def test_api_key_is_required(self):
        """api-key input should be required."""
        action_file = ACTION_DIR / "action.yml"
        content = yaml.safe_load(action_file.read_text())
        api_key = content.get("inputs", {}).get("api-key", {})
        assert api_key.get("required") is True

    def test_has_provider_input(self):
        """Action should have provider input."""
        action_file = ACTION_DIR / "action.yml"
        content = yaml.safe_load(action_file.read_text())
        inputs = content.get("inputs", {})
        assert "provider" in inputs

    def test_provider_has_default(self):
        """provider input should have default value."""
        action_file = ACTION_DIR / "action.yml"
        content = yaml.safe_load(action_file.read_text())
        provider = content.get("inputs", {}).get("provider", {})
        assert "default" in provider

    def test_has_fail_on_flaky_input(self):
        """Action should have fail-on-flaky input."""
        action_file = ACTION_DIR / "action.yml"
        content = yaml.safe_load(action_file.read_text())
        inputs = content.get("inputs", {})
        assert "fail-on-flaky" in inputs

    def test_fail_on_flaky_default_false(self):
        """fail-on-flaky should default to false."""
        action_file = ACTION_DIR / "action.yml"
        content = yaml.safe_load(action_file.read_text())
        fail_on_flaky = content.get("inputs", {}).get("fail-on-flaky", {})
        assert fail_on_flaky.get("default") == "false"


class TestActionOutputs:
    """Test action outputs configuration."""

    def test_action_has_outputs(self):
        """action.yml should have outputs section."""
        action_file = ACTION_DIR / "action.yml"
        content = yaml.safe_load(action_file.read_text())
        assert "outputs" in content

    def test_has_analysis_output(self):
        """Action should have analysis output."""
        action_file = ACTION_DIR / "action.yml"
        content = yaml.safe_load(action_file.read_text())
        outputs = content.get("outputs", {})
        assert "analysis" in outputs

    def test_has_failed_tests_count_output(self):
        """Action should have failed-tests-count output."""
        action_file = ACTION_DIR / "action.yml"
        content = yaml.safe_load(action_file.read_text())
        outputs = content.get("outputs", {})
        assert "failed-tests-count" in outputs

    def test_has_flaky_detected_output(self):
        """Action should have flaky-detected output."""
        action_file = ACTION_DIR / "action.yml"
        content = yaml.safe_load(action_file.read_text())
        outputs = content.get("outputs", {})
        assert "flaky-detected" in outputs


class TestActionRuns:
    """Test action runs configuration."""

    def test_action_has_runs(self):
        """action.yml should have runs section."""
        action_file = ACTION_DIR / "action.yml"
        content = yaml.safe_load(action_file.read_text())
        assert "runs" in content

    def test_runs_using_composite(self):
        """Action should use composite runs."""
        action_file = ACTION_DIR / "action.yml"
        content = yaml.safe_load(action_file.read_text())
        runs = content.get("runs", {})
        assert runs.get("using") == "composite"

    def test_runs_has_steps(self):
        """Composite action should have steps."""
        action_file = ACTION_DIR / "action.yml"
        content = yaml.safe_load(action_file.read_text())
        runs = content.get("runs", {})
        assert "steps" in runs
        assert len(runs["steps"]) > 0


class TestActionSteps:
    """Test action steps configuration."""

    def test_has_python_setup_step(self):
        """Action should set up Python."""
        action_file = ACTION_DIR / "action.yml"
        content = yaml.safe_load(action_file.read_text())
        steps = content.get("runs", {}).get("steps", [])
        step_uses = [s.get("uses", "") for s in steps]
        has_python = any("setup-python" in u for u in step_uses)
        assert has_python, "Action should use setup-python"

    def test_has_install_step(self):
        """Action should install heisenberg."""
        action_file = ACTION_DIR / "action.yml"
        content = yaml.safe_load(action_file.read_text())
        steps = content.get("runs", {}).get("steps", [])
        step_runs = [s.get("run", "") for s in steps]
        has_install = any("pip install" in r or "uv pip install" in r for r in step_runs)
        assert has_install, "Action should install dependencies"

    def test_has_analyze_step(self):
        """Action should run analysis."""
        action_file = ACTION_DIR / "action.yml"
        content = yaml.safe_load(action_file.read_text())
        steps = content.get("runs", {}).get("steps", [])
        step_runs = [s.get("run", "") for s in steps]
        has_analyze = any("heisenberg" in r or "analyze" in r.lower() for r in step_runs)
        assert has_analyze, "Action should run heisenberg analysis"


class TestActionReadme:
    """Test action README documentation."""

    def test_action_readme_exists(self):
        """Action should have README.md."""
        readme = ACTION_DIR / "README.md"
        assert readme.exists(), "action/README.md not found"

    def test_readme_has_usage_example(self):
        """README should have usage example."""
        readme = ACTION_DIR / "README.md"
        content = readme.read_text()
        assert "uses:" in content or "usage" in content.lower()

    def test_readme_documents_inputs(self):
        """README should document inputs."""
        readme = ACTION_DIR / "README.md"
        content = readme.read_text().lower()
        assert "input" in content or "report-path" in content

    def test_readme_documents_outputs(self):
        """README should document outputs."""
        readme = ACTION_DIR / "README.md"
        content = readme.read_text().lower()
        assert "output" in content or "analysis" in content
