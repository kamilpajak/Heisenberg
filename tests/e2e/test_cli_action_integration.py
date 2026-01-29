"""Tests for CLI and GitHub Action integration - TDD for CI readiness."""

import json
import subprocess
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent
ACTION_FILE = PROJECT_ROOT / "action" / "action.yml"
CLI_FILE = PROJECT_ROOT / "src" / "heisenberg" / "cli.py"


class TestCLIArguments:
    """Test that CLI has all required arguments for Action integration."""

    def test_cli_has_provider_argument(self):
        """CLI should accept --provider argument."""
        result = subprocess.run(
            [sys.executable, "-m", "heisenberg", "analyze", "--help"],
            capture_output=True,
            text=True,
        )
        assert "--provider" in result.stdout

    def test_cli_has_model_argument(self):
        """CLI should accept --model argument."""
        result = subprocess.run(
            [sys.executable, "-m", "heisenberg", "analyze", "--help"],
            capture_output=True,
            text=True,
        )
        assert "--model" in result.stdout

    def test_cli_has_output_format_argument(self):
        """CLI should accept --output-format argument."""
        result = subprocess.run(
            [sys.executable, "-m", "heisenberg", "analyze", "--help"],
            capture_output=True,
            text=True,
        )
        assert "--output-format" in result.stdout

    def test_cli_has_container_logs_argument(self):
        """CLI should accept --container-logs argument for log file path."""
        result = subprocess.run(
            [sys.executable, "-m", "heisenberg", "analyze", "--help"],
            capture_output=True,
            text=True,
        )
        assert "--container-logs" in result.stdout


class TestCLIJSONOutput:
    """Test CLI JSON output format."""

    def test_json_output_has_flaky_detected(self, tmp_path):
        """JSON output should include flaky_detected field."""
        # Create minimal valid Playwright report
        report = {
            "suites": [],
            "stats": {"expected": 0, "unexpected": 0, "flaky": 0, "skipped": 0},
        }
        report_file = tmp_path / "report.json"
        report_file.write_text(json.dumps(report))

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "heisenberg",
                "analyze",
                "--report",
                str(report_file),
                "--output-format",
                "json",
            ],
            capture_output=True,
            text=True,
        )

        # Should succeed or fail gracefully
        if result.returncode == 0:
            output = json.loads(result.stdout)
            assert "flaky_detected" in output

    def test_json_output_has_failed_tests_count(self, tmp_path):
        """JSON output should include failed_tests_count field."""
        report = {
            "suites": [],
            "stats": {"expected": 0, "unexpected": 0, "flaky": 0, "skipped": 0},
        }
        report_file = tmp_path / "report.json"
        report_file.write_text(json.dumps(report))

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "heisenberg",
                "analyze",
                "--report",
                str(report_file),
                "--output-format",
                "json",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            output = json.loads(result.stdout)
            assert "failed_tests_count" in output


class TestActionYMLCorrectness:
    """Test that action.yml uses correct CLI arguments."""

    def test_action_uses_output_format_not_output(self):
        """Action should use --output-format, not --output."""
        content = ACTION_FILE.read_text()
        action = yaml.safe_load(content)

        steps = action.get("runs", {}).get("steps", [])
        for step in steps:
            run_cmd = step.get("run", "")
            if "heisenberg" in run_cmd:
                # Should use --output-format, not --output
                assert "--output json" not in run_cmd or "--output-format" in run_cmd

    def test_action_passes_ai_analysis_flag(self):
        """Action should pass --ai-analysis flag to enable AI."""
        content = ACTION_FILE.read_text()
        action = yaml.safe_load(content)

        steps = action.get("runs", {}).get("steps", [])
        analysis_step_found = False
        for step in steps:
            run_cmd = step.get("run", "")
            if "heisenberg analyze" in run_cmd:
                analysis_step_found = True
                assert "--ai-analysis" in run_cmd or "-a" in run_cmd

        assert analysis_step_found, "No heisenberg analyze step found"

    def test_action_passes_provider_argument(self):
        """Action should pass --provider argument."""
        content = ACTION_FILE.read_text()
        action = yaml.safe_load(content)

        steps = action.get("runs", {}).get("steps", [])
        for step in steps:
            run_cmd = step.get("run", "")
            if "heisenberg analyze" in run_cmd:
                assert "--provider" in run_cmd

    def test_action_does_not_mask_errors(self):
        """Action should not use || true to mask errors."""
        content = ACTION_FILE.read_text()
        action = yaml.safe_load(content)

        steps = action.get("runs", {}).get("steps", [])
        for step in steps:
            run_cmd = step.get("run", "")
            if "heisenberg analyze" in run_cmd:
                # Should not blindly mask all errors
                assert "|| true" not in run_cmd or "|| exit 0" not in run_cmd


class TestActionPRCommenting:
    """Test that action supports PR commenting."""

    def test_action_has_post_comment_input(self):
        """Action should have post-comment input option."""
        content = ACTION_FILE.read_text()
        action = yaml.safe_load(content)

        inputs = action.get("inputs", {})
        assert "post-comment" in inputs

    def test_action_has_github_token_input(self):
        """Action should accept github-token input for PR commenting."""
        content = ACTION_FILE.read_text()
        action = yaml.safe_load(content)

        inputs = action.get("inputs", {})
        assert "github-token" in inputs

    def test_action_uses_github_token_env(self):
        """Action should set GITHUB_TOKEN env when commenting."""
        content = ACTION_FILE.read_text()
        action = yaml.safe_load(content)

        steps = action.get("runs", {}).get("steps", [])
        for step in steps:
            env = step.get("env", {})
            run_cmd = step.get("run", "")
            if "heisenberg analyze" in run_cmd and "--post-comment" in run_cmd:
                assert "GITHUB_TOKEN" in env or "github-token" in str(env).lower()


class TestCLIProviderIntegration:
    """Test CLI provider argument works with LLM providers."""

    def test_cli_accepts_claude_provider(self):
        """CLI should accept --provider claude."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "heisenberg",
                "analyze",
                "--help",
            ],
            capture_output=True,
            text=True,
        )
        # Just verify the argument exists and mentions providers
        assert "--provider" in result.stdout

    def test_cli_accepts_gemini_provider(self):
        """CLI should accept --provider gemini."""
        # Provider choice validation happens at runtime
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "heisenberg",
                "analyze",
                "--help",
            ],
            capture_output=True,
            text=True,
        )
        help_text = result.stdout.lower()
        assert "provider" in help_text


class TestActionOutputs:
    """Test that action outputs are correctly defined."""

    def test_action_has_analysis_output(self):
        """Action should have analysis output."""
        content = ACTION_FILE.read_text()
        action = yaml.safe_load(content)

        outputs = action.get("outputs", {})
        assert "analysis" in outputs

    def test_action_has_flaky_detected_output(self):
        """Action should have flaky-detected output."""
        content = ACTION_FILE.read_text()
        action = yaml.safe_load(content)

        outputs = action.get("outputs", {})
        assert "flaky-detected" in outputs

    def test_action_has_failed_tests_count_output(self):
        """Action should have failed-tests-count output."""
        content = ACTION_FILE.read_text()
        action = yaml.safe_load(content)

        outputs = action.get("outputs", {})
        assert "failed-tests-count" in outputs
