"""Tests for project documentation - TDD for Phase 3."""

from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).parent.parent


class TestReadmeStructure:
    """Validate README.md has all required sections for GitHub Marketplace."""

    @pytest.fixture
    def readme_content(self) -> str:
        """Load README.md content."""
        readme_path = PROJECT_ROOT / "README.md"
        return readme_path.read_text()

    def test_readme_has_title(self, readme_content: str):
        """README should have a main title."""
        assert "# " in readme_content

    def test_readme_has_badges(self, readme_content: str):
        """README should have status badges."""
        assert "![" in readme_content or "[![" in readme_content

    def test_readme_has_overview_section(self, readme_content: str):
        """README should have an overview/about section."""
        lower = readme_content.lower()
        assert "## overview" in lower or "## about" in lower

    def test_readme_has_features_section(self, readme_content: str):
        """README should list features."""
        lower = readme_content.lower()
        assert "## features" in lower or "## key features" in lower

    def test_readme_has_quickstart_section(self, readme_content: str):
        """README should have a quick start guide."""
        lower = readme_content.lower()
        assert (
            "## quick start" in lower or "## quickstart" in lower or "## getting started" in lower
        )

    def test_readme_has_installation_section(self, readme_content: str):
        """README should have installation instructions."""
        assert "## installation" in readme_content.lower()

    def test_readme_has_usage_section(self, readme_content: str):
        """README should have usage examples."""
        assert "## usage" in readme_content.lower()

    def test_readme_has_configuration_section(self, readme_content: str):
        """README should document configuration options."""
        lower = readme_content.lower()
        assert "## configuration" in lower or "## options" in lower or "## inputs" in lower

    def test_readme_has_workflow_example(self, readme_content: str):
        """README should show a complete workflow example."""
        # Should contain a YAML workflow example
        assert "```yaml" in readme_content
        assert "uses:" in readme_content

    def test_readme_has_ai_feature_documented(self, readme_content: str):
        """README should document the AI analysis feature."""
        lower = readme_content.lower()
        assert "ai" in lower and ("analysis" in lower or "diagnosis" in lower)

    def test_readme_has_license_section(self, readme_content: str):
        """README should mention the license."""
        assert "## license" in readme_content.lower()

    def test_readme_has_contributing_reference(self, readme_content: str):
        """README should reference CONTRIBUTING.md."""
        lower = readme_content.lower()
        assert "contributing" in lower


class TestContributing:
    """Validate CONTRIBUTING.md exists and has required content."""

    @pytest.fixture
    def contributing_content(self) -> str:
        """Load CONTRIBUTING.md content."""
        contributing_path = PROJECT_ROOT / "CONTRIBUTING.md"
        assert contributing_path.exists(), "CONTRIBUTING.md must exist"
        return contributing_path.read_text()

    def test_contributing_has_title(self, contributing_content: str):
        """CONTRIBUTING.md should have a title."""
        assert "# Contributing" in contributing_content

    def test_contributing_has_setup_section(self, contributing_content: str):
        """CONTRIBUTING.md should explain development setup."""
        lower = contributing_content.lower()
        assert "setup" in lower or "development" in lower

    def test_contributing_has_testing_section(self, contributing_content: str):
        """CONTRIBUTING.md should explain how to run tests."""
        lower = contributing_content.lower()
        assert "test" in lower

    def test_contributing_has_code_style_section(self, contributing_content: str):
        """CONTRIBUTING.md should document code style expectations."""
        lower = contributing_content.lower()
        assert "style" in lower or "lint" in lower or "ruff" in lower

    def test_contributing_has_pr_guidelines(self, contributing_content: str):
        """CONTRIBUTING.md should have PR guidelines."""
        lower = contributing_content.lower()
        assert "pull request" in lower or "pr" in lower


class TestGitHubIssueTemplates:
    """Validate GitHub Issue templates exist and are valid."""

    def test_issue_templates_directory_exists(self):
        """Issue templates directory should exist."""
        templates_dir = PROJECT_ROOT / ".github" / "ISSUE_TEMPLATE"
        assert templates_dir.exists(), ".github/ISSUE_TEMPLATE directory must exist"

    def test_bug_report_template_exists(self):
        """Bug report template should exist."""
        bug_template = PROJECT_ROOT / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml"
        assert bug_template.exists(), "Bug report template must exist"

    def test_feature_request_template_exists(self):
        """Feature request template should exist."""
        feature_template = PROJECT_ROOT / ".github" / "ISSUE_TEMPLATE" / "feature_request.yml"
        assert feature_template.exists(), "Feature request template must exist"

    def test_bug_report_template_is_valid_yaml(self):
        """Bug report template should be valid YAML."""
        bug_template = PROJECT_ROOT / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml"
        content = bug_template.read_text()
        parsed = yaml.safe_load(content)
        assert "name" in parsed
        assert "body" in parsed

    def test_feature_request_template_is_valid_yaml(self):
        """Feature request template should be valid YAML."""
        feature_template = PROJECT_ROOT / ".github" / "ISSUE_TEMPLATE" / "feature_request.yml"
        content = feature_template.read_text()
        parsed = yaml.safe_load(content)
        assert "name" in parsed
        assert "body" in parsed


class TestActionYmlForMarketplace:
    """Validate action.yml meets GitHub Marketplace requirements."""

    @pytest.fixture
    def action_content(self) -> dict:
        """Load action.yml content."""
        action_path = PROJECT_ROOT / "action.yml"
        return yaml.safe_load(action_path.read_text())

    def test_action_has_name(self, action_content: dict):
        """action.yml must have a name."""
        assert "name" in action_content
        assert len(action_content["name"]) > 0

    def test_action_has_description(self, action_content: dict):
        """action.yml must have a description."""
        assert "description" in action_content
        assert len(action_content["description"]) > 0

    def test_action_has_author(self, action_content: dict):
        """action.yml must have an author."""
        assert "author" in action_content

    def test_action_has_branding(self, action_content: dict):
        """action.yml must have branding for Marketplace."""
        assert "branding" in action_content
        assert "icon" in action_content["branding"]
        assert "color" in action_content["branding"]

    def test_action_branding_icon_is_valid(self, action_content: dict):
        """action.yml branding icon must be from Feather icons."""
        # Partial list of valid Feather icons
        valid_icons = [
            "activity",
            "airplay",
            "alert-circle",
            "alert-octagon",
            "alert-triangle",
            "archive",
            "arrow-down",
            "arrow-left",
            "arrow-right",
            "arrow-up",
            "award",
            "book",
            "box",
            "check",
            "check-circle",
            "clipboard",
            "code",
            "cpu",
            "database",
            "eye",
            "file",
            "filter",
            "flag",
            "folder",
            "git-branch",
            "git-commit",
            "git-merge",
            "git-pull-request",
            "globe",
            "heart",
            "help-circle",
            "home",
            "info",
            "layers",
            "layout",
            "link",
            "list",
            "lock",
            "mail",
            "map",
            "maximize",
            "message-circle",
            "mic",
            "monitor",
            "moon",
            "package",
            "play",
            "plus",
            "plus-circle",
            "power",
            "radio",
            "refresh-cw",
            "save",
            "search",
            "send",
            "server",
            "settings",
            "shield",
            "star",
            "sun",
            "tag",
            "target",
            "terminal",
            "thumbs-up",
            "tool",
            "trash",
            "trending-up",
            "user",
            "users",
            "x",
            "zap",
        ]
        assert action_content["branding"]["icon"] in valid_icons

    def test_action_branding_color_is_valid(self, action_content: dict):
        """action.yml branding color must be valid."""
        valid_colors = ["white", "yellow", "blue", "green", "orange", "red", "purple", "gray-dark"]
        assert action_content["branding"]["color"] in valid_colors

    def test_action_has_inputs(self, action_content: dict):
        """action.yml must have inputs defined."""
        assert "inputs" in action_content
        assert len(action_content["inputs"]) > 0

    def test_action_inputs_have_descriptions(self, action_content: dict):
        """All inputs must have descriptions."""
        for input_name, input_def in action_content["inputs"].items():
            assert "description" in input_def, f"Input '{input_name}' must have description"

    def test_action_has_outputs(self, action_content: dict):
        """action.yml should have outputs defined."""
        assert "outputs" in action_content
        assert len(action_content["outputs"]) > 0

    def test_action_outputs_have_descriptions(self, action_content: dict):
        """All outputs must have descriptions."""
        for output_name, output_def in action_content["outputs"].items():
            assert "description" in output_def, f"Output '{output_name}' must have description"
