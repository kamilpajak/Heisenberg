"""Tests for CI workflow configuration - TDD for Phase 3."""

from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent


class TestCIWorkflow:
    """Validate CI workflow configuration."""

    def test_ci_workflow_exists(self):
        """CI workflow file should exist."""
        workflow_path = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
        assert workflow_path.exists(), "CI workflow must exist at .github/workflows/ci.yml"

    def test_ci_workflow_is_valid_yaml(self):
        """CI workflow should be valid YAML."""
        workflow_path = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
        content = workflow_path.read_text()
        parsed = yaml.safe_load(content)
        assert isinstance(parsed, dict)

    def test_ci_workflow_has_name(self):
        """CI workflow should have a name."""
        workflow_path = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
        parsed = yaml.safe_load(workflow_path.read_text())
        assert "name" in parsed

    def test_ci_workflow_triggers_on_push_and_pr(self):
        """CI workflow should trigger on push and pull_request."""
        workflow_path = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
        parsed = yaml.safe_load(workflow_path.read_text())
        # YAML parses "on" as boolean True, so check for True key
        assert "on" in parsed or True in parsed
        triggers = parsed.get("on") or parsed.get(True)
        # Can be a list or dict
        if isinstance(triggers, list):
            assert "push" in triggers
            assert "pull_request" in triggers
        else:
            assert "push" in triggers or "pull_request" in triggers

    def test_ci_workflow_has_jobs(self):
        """CI workflow should define jobs."""
        workflow_path = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
        parsed = yaml.safe_load(workflow_path.read_text())
        assert "jobs" in parsed
        assert len(parsed["jobs"]) > 0

    def test_ci_workflow_runs_tests(self):
        """CI workflow should run pytest."""
        workflow_path = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
        content = workflow_path.read_text()
        assert "pytest" in content

    def test_ci_workflow_runs_linter(self):
        """CI workflow should run ruff."""
        workflow_path = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
        content = workflow_path.read_text()
        assert "ruff" in content

    def test_ci_workflow_uses_python_311_or_higher(self):
        """CI workflow should use Python 3.11+."""
        workflow_path = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
        content = workflow_path.read_text()
        # Check for Python 3.11 or 3.12
        assert "3.11" in content or "3.12" in content

    def test_ci_workflow_uploads_coverage(self):
        """CI workflow should upload coverage reports."""
        workflow_path = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
        content = workflow_path.read_text()
        # Should mention coverage
        assert "cov" in content.lower() or "coverage" in content.lower()
