"""Tests for CI/CD pipeline configuration - TDD for Phase 8."""

from pathlib import Path

import yaml

# Project root
PROJECT_ROOT = Path(__file__).parent.parent
WORKFLOWS_DIR = PROJECT_ROOT / ".github" / "workflows"


class TestWorkflowsDirectoryExists:
    """Test that GitHub Actions workflows directory exists."""

    def test_github_directory_exists(self):
        """.github directory should exist."""
        github_dir = PROJECT_ROOT / ".github"
        assert github_dir.exists(), ".github directory not found"

    def test_workflows_directory_exists(self):
        """.github/workflows directory should exist."""
        assert WORKFLOWS_DIR.exists(), ".github/workflows directory not found"


class TestCIWorkflow:
    """Test CI workflow configuration."""

    def test_ci_workflow_exists(self):
        """CI workflow file should exist."""
        ci_files = list(WORKFLOWS_DIR.glob("ci*.yml")) + list(WORKFLOWS_DIR.glob("ci*.yaml"))
        assert len(ci_files) > 0, "No CI workflow file found"

    def test_ci_workflow_is_valid_yaml(self):
        """CI workflow should be valid YAML."""
        ci_files = list(WORKFLOWS_DIR.glob("ci*.yml")) + list(WORKFLOWS_DIR.glob("ci*.yaml"))
        for ci_file in ci_files:
            content = yaml.safe_load(ci_file.read_text())
            assert content is not None

    def test_ci_workflow_has_name(self):
        """CI workflow should have a name."""
        ci_files = list(WORKFLOWS_DIR.glob("ci*.yml")) + list(WORKFLOWS_DIR.glob("ci*.yaml"))
        for ci_file in ci_files:
            content = yaml.safe_load(ci_file.read_text())
            assert "name" in content

    def test_ci_workflow_has_triggers(self):
        """CI workflow should have triggers (on)."""
        ci_files = list(WORKFLOWS_DIR.glob("ci*.yml")) + list(WORKFLOWS_DIR.glob("ci*.yaml"))
        for ci_file in ci_files:
            content = yaml.safe_load(ci_file.read_text())
            assert "on" in content or True in content  # 'on' or True (yaml boolean)

    def test_ci_workflow_triggers_on_push(self):
        """CI workflow should trigger on push."""
        ci_files = list(WORKFLOWS_DIR.glob("ci*.yml")) + list(WORKFLOWS_DIR.glob("ci*.yaml"))
        for ci_file in ci_files:
            content = yaml.safe_load(ci_file.read_text())
            triggers = content.get("on") or content.get(True)
            assert "push" in triggers or isinstance(triggers, list) and "push" in triggers

    def test_ci_workflow_triggers_on_pull_request(self):
        """CI workflow should trigger on pull_request."""
        ci_files = list(WORKFLOWS_DIR.glob("ci*.yml")) + list(WORKFLOWS_DIR.glob("ci*.yaml"))
        for ci_file in ci_files:
            content = yaml.safe_load(ci_file.read_text())
            triggers = content.get("on") or content.get(True)
            assert "pull_request" in triggers

    def test_ci_workflow_has_jobs(self):
        """CI workflow should have jobs defined."""
        ci_files = list(WORKFLOWS_DIR.glob("ci*.yml")) + list(WORKFLOWS_DIR.glob("ci*.yaml"))
        for ci_file in ci_files:
            content = yaml.safe_load(ci_file.read_text())
            assert "jobs" in content
            assert len(content["jobs"]) > 0


class TestTestJob:
    """Test the test job configuration."""

    def test_ci_has_test_job(self):
        """CI workflow should have a test job."""
        ci_files = list(WORKFLOWS_DIR.glob("ci*.yml")) + list(WORKFLOWS_DIR.glob("ci*.yaml"))
        for ci_file in ci_files:
            content = yaml.safe_load(ci_file.read_text())
            jobs = content.get("jobs", {})
            # Should have test, tests, or pytest job
            test_jobs = [j for j in jobs.keys() if "test" in j.lower()]
            assert len(test_jobs) > 0, "No test job found"

    def test_test_job_runs_on_ubuntu(self):
        """Test job should run on ubuntu."""
        ci_files = list(WORKFLOWS_DIR.glob("ci*.yml")) + list(WORKFLOWS_DIR.glob("ci*.yaml"))
        for ci_file in ci_files:
            content = yaml.safe_load(ci_file.read_text())
            jobs = content.get("jobs", {})
            for job_name, job_config in jobs.items():
                if "test" in job_name.lower():
                    runs_on = job_config.get("runs-on", "")
                    assert "ubuntu" in runs_on.lower()

    def test_test_job_uses_python(self):
        """Test job should set up Python."""
        ci_files = list(WORKFLOWS_DIR.glob("ci*.yml")) + list(WORKFLOWS_DIR.glob("ci*.yaml"))
        for ci_file in ci_files:
            content = yaml.safe_load(ci_file.read_text())
            jobs = content.get("jobs", {})
            for job_name, job_config in jobs.items():
                if "test" in job_name.lower():
                    steps = job_config.get("steps", [])
                    step_uses = [s.get("uses", "") for s in steps]
                    has_python = any("python" in u.lower() for u in step_uses)
                    assert has_python, "Test job should use Python setup action"

    def test_test_job_runs_pytest(self):
        """Test job should run pytest."""
        ci_files = list(WORKFLOWS_DIR.glob("ci*.yml")) + list(WORKFLOWS_DIR.glob("ci*.yaml"))
        for ci_file in ci_files:
            content = yaml.safe_load(ci_file.read_text())
            jobs = content.get("jobs", {})
            for job_name, job_config in jobs.items():
                if "test" in job_name.lower():
                    steps = job_config.get("steps", [])
                    step_runs = [s.get("run", "") for s in steps]
                    has_pytest = any("pytest" in r for r in step_runs)
                    assert has_pytest, "Test job should run pytest"


class TestLintJob:
    """Test the lint job configuration."""

    def test_ci_has_lint_job(self):
        """CI workflow should have a lint job."""
        ci_files = list(WORKFLOWS_DIR.glob("ci*.yml")) + list(WORKFLOWS_DIR.glob("ci*.yaml"))
        for ci_file in ci_files:
            content = yaml.safe_load(ci_file.read_text())
            jobs = content.get("jobs", {})
            # Should have lint, linting, or ruff job
            lint_jobs = [j for j in jobs.keys() if "lint" in j.lower() or "ruff" in j.lower()]
            assert len(lint_jobs) > 0, "No lint job found"

    def test_lint_job_runs_ruff(self):
        """Lint job should run ruff."""
        ci_files = list(WORKFLOWS_DIR.glob("ci*.yml")) + list(WORKFLOWS_DIR.glob("ci*.yaml"))
        for ci_file in ci_files:
            content = yaml.safe_load(ci_file.read_text())
            jobs = content.get("jobs", {})
            for job_name, job_config in jobs.items():
                if "lint" in job_name.lower() or "ruff" in job_name.lower():
                    steps = job_config.get("steps", [])
                    step_runs = [s.get("run", "") for s in steps]
                    step_uses = [s.get("uses", "") for s in steps]
                    has_ruff = any("ruff" in r for r in step_runs) or any(
                        "ruff" in u for u in step_uses
                    )
                    assert has_ruff, "Lint job should run ruff"


class TestBuildJob:
    """Test Docker build job configuration."""

    def test_ci_has_build_job(self):
        """CI workflow should have a build job."""
        ci_files = list(WORKFLOWS_DIR.glob("ci*.yml")) + list(WORKFLOWS_DIR.glob("ci*.yaml"))
        has_build = False
        for ci_file in ci_files:
            content = yaml.safe_load(ci_file.read_text())
            jobs = content.get("jobs", {})
            build_jobs = [j for j in jobs.keys() if "build" in j.lower() or "docker" in j.lower()]
            if len(build_jobs) > 0:
                has_build = True
        assert has_build, "No build job found in any workflow"

    def test_build_job_builds_docker(self):
        """Build job should build Docker image."""
        ci_files = list(WORKFLOWS_DIR.glob("ci*.yml")) + list(WORKFLOWS_DIR.glob("ci*.yaml"))
        for ci_file in ci_files:
            content = yaml.safe_load(ci_file.read_text())
            jobs = content.get("jobs", {})
            for job_name, job_config in jobs.items():
                if "build" in job_name.lower() or "docker" in job_name.lower():
                    steps = job_config.get("steps", [])
                    step_runs = [s.get("run", "") for s in steps]
                    step_uses = [s.get("uses", "") for s in steps]
                    has_docker = any("docker" in r.lower() for r in step_runs) or any(
                        "docker" in u.lower() for u in step_uses
                    )
                    assert has_docker, "Build job should use Docker"


class TestDependabotConfig:
    """Test Dependabot configuration."""

    def test_dependabot_config_exists(self):
        """Dependabot config should exist."""
        dependabot_file = PROJECT_ROOT / ".github" / "dependabot.yml"
        assert dependabot_file.exists(), "dependabot.yml not found"

    def test_dependabot_config_is_valid_yaml(self):
        """Dependabot config should be valid YAML."""
        dependabot_file = PROJECT_ROOT / ".github" / "dependabot.yml"
        content = yaml.safe_load(dependabot_file.read_text())
        assert content is not None

    def test_dependabot_has_version(self):
        """Dependabot config should have version."""
        dependabot_file = PROJECT_ROOT / ".github" / "dependabot.yml"
        content = yaml.safe_load(dependabot_file.read_text())
        assert "version" in content
        assert content["version"] == 2

    def test_dependabot_has_updates(self):
        """Dependabot config should have updates section."""
        dependabot_file = PROJECT_ROOT / ".github" / "dependabot.yml"
        content = yaml.safe_load(dependabot_file.read_text())
        assert "updates" in content
        assert len(content["updates"]) > 0

    def test_dependabot_monitors_pip(self):
        """Dependabot should monitor pip dependencies."""
        dependabot_file = PROJECT_ROOT / ".github" / "dependabot.yml"
        content = yaml.safe_load(dependabot_file.read_text())
        ecosystems = [u.get("package-ecosystem") for u in content.get("updates", [])]
        assert "pip" in ecosystems, "Dependabot should monitor pip"

    def test_dependabot_monitors_github_actions(self):
        """Dependabot should monitor GitHub Actions."""
        dependabot_file = PROJECT_ROOT / ".github" / "dependabot.yml"
        content = yaml.safe_load(dependabot_file.read_text())
        ecosystems = [u.get("package-ecosystem") for u in content.get("updates", [])]
        assert "github-actions" in ecosystems, "Dependabot should monitor github-actions"
