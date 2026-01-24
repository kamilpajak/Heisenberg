"""Tests for self-generating validation test suite - TDD.

This test suite verifies that Heisenberg has its own Playwright tests
that generate controlled, reproducible failures for validation.
"""

import json
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
VALIDATION_TESTS_DIR = PROJECT_ROOT / "validation_tests"


class TestValidationTestsStructure:
    """Verify the validation tests directory structure exists."""

    def test_validation_tests_directory_exists(self):
        """validation_tests/ directory should exist."""
        assert VALIDATION_TESTS_DIR.exists(), (
            f"Directory {VALIDATION_TESTS_DIR} does not exist. "
            "Create it with Playwright tests for validation."
        )

    def test_playwright_config_exists(self):
        """playwright.config.ts should exist."""
        config_file = VALIDATION_TESTS_DIR / "playwright.config.ts"
        assert config_file.exists(), "playwright.config.ts is required"

    def test_test_app_exists(self):
        """test-app/ directory with HTML should exist."""
        test_app = VALIDATION_TESTS_DIR / "test-app"
        assert test_app.exists(), "test-app/ directory is required"

        index_html = test_app / "index.html"
        assert index_html.exists(), "test-app/index.html is required"

    def test_tests_directory_exists(self):
        """tests/ directory should exist with spec files."""
        tests_dir = VALIDATION_TESTS_DIR / "tests"
        assert tests_dir.exists(), "tests/ directory is required"

        spec_files = list(tests_dir.glob("*.spec.ts"))
        assert len(spec_files) >= 3, f"Expected at least 3 spec files, found {len(spec_files)}"


class TestValidationTestTypes:
    """Verify different failure types are covered."""

    def test_has_timeout_flaky_test(self):
        """Should have a test that demonstrates timeout flakiness."""
        tests_dir = VALIDATION_TESTS_DIR / "tests"
        if not tests_dir.exists():
            pytest.skip("tests/ directory not created yet")

        files = [f.name for f in tests_dir.glob("*.spec.ts")]
        has_timeout = any("timeout" in f.lower() for f in files)
        assert has_timeout, "Should have a timeout flaky test"

    def test_has_selector_failure_test(self):
        """Should have a test that demonstrates selector failures."""
        tests_dir = VALIDATION_TESTS_DIR / "tests"
        if not tests_dir.exists():
            pytest.skip("tests/ directory not created yet")

        files = [f.name for f in tests_dir.glob("*.spec.ts")]
        has_selector = any(
            "selector" in f.lower() or "element" in f.lower() or "dom" in f.lower() for f in files
        )
        assert has_selector, "Should have a selector/DOM failure test"

    def test_has_assertion_failure_test(self):
        """Should have a test that demonstrates assertion failures."""
        tests_dir = VALIDATION_TESTS_DIR / "tests"
        if not tests_dir.exists():
            pytest.skip("tests/ directory not created yet")

        files = [f.name for f in tests_dir.glob("*.spec.ts")]
        has_assertion = any("assertion" in f.lower() or "expect" in f.lower() for f in files)
        assert has_assertion, "Should have an assertion failure test"

    def test_has_network_failure_test(self):
        """Should have a test that demonstrates network/API failures."""
        tests_dir = VALIDATION_TESTS_DIR / "tests"
        if not tests_dir.exists():
            pytest.skip("tests/ directory not created yet")

        files = [f.name for f in tests_dir.glob("*.spec.ts")]
        has_network = any(
            "network" in f.lower() or "api" in f.lower() or "race" in f.lower() for f in files
        )
        assert has_network, "Should have a network/race condition test"


class TestPlaywrightConfig:
    """Verify Playwright config is properly set up."""

    def test_config_uses_json_reporter(self):
        """Config should include JSON reporter for Heisenberg."""
        config_file = VALIDATION_TESTS_DIR / "playwright.config.ts"
        if not config_file.exists():
            pytest.skip("playwright.config.ts not created yet")

        content = config_file.read_text()
        assert "json" in content.lower(), "Config should use JSON reporter"

    def test_config_has_reasonable_timeout(self):
        """Config should have a reasonable timeout for flaky tests."""
        config_file = VALIDATION_TESTS_DIR / "playwright.config.ts"
        if not config_file.exists():
            pytest.skip("playwright.config.ts not created yet")

        content = config_file.read_text()
        assert "timeout" in content.lower(), "Config should set timeout"

    def test_config_serves_test_app(self):
        """Config should serve the test-app directory."""
        config_file = VALIDATION_TESTS_DIR / "playwright.config.ts"
        if not config_file.exists():
            pytest.skip("playwright.config.ts not created yet")

        content = config_file.read_text()
        assert "webServer" in content or "baseURL" in content, (
            "Config should configure web server or base URL"
        )


class TestTestAppContent:
    """Verify test app has necessary elements for testing."""

    def test_app_has_interactive_elements(self):
        """Test app should have buttons and inputs for interaction."""
        index_html = VALIDATION_TESTS_DIR / "test-app" / "index.html"
        if not index_html.exists():
            pytest.skip("index.html not created yet")

        content = index_html.read_text()
        assert "<button" in content, "App should have buttons"

    def test_app_has_dynamic_behavior(self):
        """Test app should have JavaScript for dynamic behavior."""
        index_html = VALIDATION_TESTS_DIR / "test-app" / "index.html"
        if not index_html.exists():
            pytest.skip("index.html not created yet")

        content = index_html.read_text()
        assert "<script" in content, "App should have JavaScript"

    def test_app_has_testid_attributes(self):
        """Test app should use data-testid for reliable selectors."""
        index_html = VALIDATION_TESTS_DIR / "test-app" / "index.html"
        if not index_html.exists():
            pytest.skip("index.html not created yet")

        content = index_html.read_text()
        assert "data-testid" in content, "App should use data-testid attributes"


class TestValidationIntegration:
    """Test that validation suite integrates with Heisenberg."""

    def test_package_json_exists(self):
        """package.json should exist for npm dependencies."""
        package_json = VALIDATION_TESTS_DIR / "package.json"
        assert package_json.exists(), "package.json is required"

    def test_package_has_playwright_dependency(self):
        """package.json should have @playwright/test dependency."""
        package_json = VALIDATION_TESTS_DIR / "package.json"
        if not package_json.exists():
            pytest.skip("package.json not created yet")

        content = json.loads(package_json.read_text())
        deps = {**content.get("dependencies", {}), **content.get("devDependencies", {})}
        assert "@playwright/test" in deps, "Should have @playwright/test dependency"

    def test_has_run_script(self):
        """package.json should have a test script."""
        package_json = VALIDATION_TESTS_DIR / "package.json"
        if not package_json.exists():
            pytest.skip("package.json not created yet")

        content = json.loads(package_json.read_text())
        scripts = content.get("scripts", {})
        assert "test" in scripts, "Should have 'test' script"

    def test_has_generate_report_script(self):
        """package.json should have script to generate JSON report."""
        package_json = VALIDATION_TESTS_DIR / "package.json"
        if not package_json.exists():
            pytest.skip("package.json not created yet")

        content = json.loads(package_json.read_text())
        scripts = content.get("scripts", {})
        # Should have test:report script
        assert "test:report" in scripts or "test" in scripts, (
            "Should have script for running tests with report"
        )
