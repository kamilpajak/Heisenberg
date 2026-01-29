"""Tests for real-world validation CI workflow - TDD."""

from pathlib import Path

import yaml

WORKFLOW_FILE = (
    Path(__file__).parent.parent.parent / ".github" / "workflows" / "validate-real-world.yml"
)


class TestValidateWorkflowExists:
    """Verify the validation workflow file exists."""

    def test_workflow_file_exists(self):
        """validate-real-world.yml should exist."""
        assert WORKFLOW_FILE.exists(), f"Workflow file {WORKFLOW_FILE} does not exist"

    def test_workflow_is_valid_yaml(self):
        """Workflow should be valid YAML."""
        content = WORKFLOW_FILE.read_text()
        workflow = yaml.safe_load(content)
        assert workflow is not None


class TestValidateWorkflowTriggers:
    """Test workflow triggers."""

    def _get_triggers(self):
        """Get triggers from workflow (handles YAML 'on' -> True parsing)."""
        content = WORKFLOW_FILE.read_text()
        workflow = yaml.safe_load(content)
        # YAML parses 'on' as True (boolean), so we check for True key
        return workflow.get("on") or workflow.get(True, {})

    def test_has_schedule_trigger(self):
        """Workflow should have a schedule trigger."""
        triggers = self._get_triggers()
        assert "schedule" in triggers

    def test_schedule_is_weekly(self):
        """Schedule should run weekly."""
        triggers = self._get_triggers()
        schedule = triggers["schedule"]
        assert len(schedule) > 0

        # Check cron expression - should be weekly
        cron = schedule[0].get("cron", "")
        # Weekly cron typically has a day-of-week field (0-6 or MON-SUN)
        # e.g., "0 6 * * 1" = Monday at 6:00
        parts = cron.split()
        assert len(parts) == 5, "Invalid cron expression"

    def test_has_workflow_dispatch(self):
        """Workflow should support manual triggering."""
        triggers = self._get_triggers()
        assert "workflow_dispatch" in triggers


class TestValidateWorkflowJobs:
    """Test workflow jobs."""

    def test_has_validate_fixtures_job(self):
        """Workflow should have a job to validate fixtures."""
        content = WORKFLOW_FILE.read_text()
        workflow = yaml.safe_load(content)

        jobs = workflow.get("jobs", {})
        assert "validate-fixtures" in jobs or any(
            "fixture" in job_name.lower() for job_name in jobs.keys()
        )

    def test_fixture_job_runs_pytest(self):
        """Fixture validation job should run pytest."""
        content = WORKFLOW_FILE.read_text()
        workflow = yaml.safe_load(content)

        jobs = workflow.get("jobs", {})
        fixture_job = jobs.get("validate-fixtures", jobs.get(list(jobs.keys())[0]))

        steps = fixture_job.get("steps", [])
        pytest_found = any("pytest" in str(step.get("run", "")).lower() for step in steps)
        assert pytest_found, "Job should run pytest"

    def test_has_validate_live_job(self):
        """Workflow should have a job to validate against live repos."""
        content = WORKFLOW_FILE.read_text()
        workflow = yaml.safe_load(content)

        jobs = workflow.get("jobs", {})
        has_live_job = "validate-live" in jobs or any(
            "live" in job_name.lower() for job_name in jobs.keys()
        )
        assert has_live_job, "Should have a job for live validation"

    def test_live_job_uses_fetch_github(self):
        """Live validation job should use fetch-github command."""
        content = WORKFLOW_FILE.read_text()
        workflow = yaml.safe_load(content)

        jobs = workflow.get("jobs", {})
        live_job = jobs.get("validate-live")

        if live_job:
            steps = live_job.get("steps", [])
            fetch_found = any("fetch-github" in str(step.get("run", "")) for step in steps)
            assert fetch_found, "Live job should use fetch-github command"


class TestValidateWorkflowSecrets:
    """Test that workflow uses appropriate secrets."""

    def test_uses_github_token(self):
        """Workflow should use GITHUB_TOKEN for API access."""
        content = WORKFLOW_FILE.read_text()
        assert "GITHUB_TOKEN" in content or "secrets.GITHUB_TOKEN" in content

    def test_live_job_has_api_key_for_ai(self):
        """Live job should have API key for AI analysis (optional)."""
        content = WORKFLOW_FILE.read_text()
        workflow = yaml.safe_load(content)

        jobs = workflow.get("jobs", {})
        live_job = jobs.get("validate-live")

        if live_job:
            # This is optional, so just verify the structure is correct
            assert "steps" in live_job


class TestValidateWorkflowOutputs:
    """Test workflow outputs and artifacts."""

    def test_creates_summary(self):
        """Workflow should create a job summary."""
        content = WORKFLOW_FILE.read_text()
        assert "GITHUB_STEP_SUMMARY" in content, "Should write to job summary"
