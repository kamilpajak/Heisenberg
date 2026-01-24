"""Tests for real-world Playwright report fixtures - TDD Red-Green-Refactor.

These tests validate that Heisenberg can handle real Playwright reports
from actual open-source projects like Cal.com, Grafana, etc.
"""

import json
from pathlib import Path

import pytest

from heisenberg.playwright_parser import parse_playwright_report

# Path to real-world fixtures
REAL_WORLD_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "real-world"

# Expected failure types that should be represented
EXPECTED_FAILURE_TYPES = {
    "timeout",
    "selector",
    "assertion",
    "network",
    "flaky",
}

# Minimum number of projects to have fixtures from
MIN_PROJECTS = 2

# Minimum number of different failure types
MIN_FAILURE_TYPES = 3


def get_all_fixture_paths() -> list[Path]:
    """Get all JSON fixture files from real-world directory."""
    if not REAL_WORLD_FIXTURES_DIR.exists():
        return []
    return list(REAL_WORLD_FIXTURES_DIR.glob("**/*.json"))


def get_project_directories() -> list[Path]:
    """Get all project directories in real-world fixtures."""
    if not REAL_WORLD_FIXTURES_DIR.exists():
        return []
    return [d for d in REAL_WORLD_FIXTURES_DIR.iterdir() if d.is_dir()]


def get_failure_type_from_filename(path: Path) -> str | None:
    """Extract failure type from fixture filename."""
    name = path.stem.lower()
    for failure_type in EXPECTED_FAILURE_TYPES:
        if failure_type in name:
            return failure_type
    return None


class TestRealWorldFixturesExist:
    """Verify that real-world fixtures directory and files exist."""

    def test_fixtures_directory_exists(self):
        """Real-world fixtures directory should exist."""
        assert REAL_WORLD_FIXTURES_DIR.exists(), (
            f"Directory {REAL_WORLD_FIXTURES_DIR} does not exist. "
            "Create it and add real Playwright reports from open-source projects."
        )

    def test_fixtures_directory_has_readme(self):
        """Fixtures directory should have README documenting sources."""
        readme = REAL_WORLD_FIXTURES_DIR / "README.md"
        assert readme.exists(), (
            "README.md should exist in fixtures/real-world/ "
            "documenting the source of each fixture."
        )

    def test_at_least_min_projects_represented(self):
        """Should have fixtures from at least MIN_PROJECTS different projects."""
        projects = get_project_directories()
        assert len(projects) >= MIN_PROJECTS, (
            f"Expected at least {MIN_PROJECTS} project directories, "
            f"found {len(projects)}: {[p.name for p in projects]}"
        )

    def test_at_least_min_failure_types_represented(self):
        """Should have at least MIN_FAILURE_TYPES different failure types."""
        fixtures = get_all_fixture_paths()
        failure_types = set()
        for fixture in fixtures:
            ft = get_failure_type_from_filename(fixture)
            if ft:
                failure_types.add(ft)

        assert len(failure_types) >= MIN_FAILURE_TYPES, (
            f"Expected at least {MIN_FAILURE_TYPES} failure types, "
            f"found {len(failure_types)}: {failure_types}. "
            f"Expected types: {EXPECTED_FAILURE_TYPES}"
        )

    def test_each_fixture_is_valid_json(self):
        """Each fixture file should contain valid JSON."""
        fixtures = get_all_fixture_paths()
        assert len(fixtures) > 0, "No fixture files found"

        for fixture in fixtures:
            try:
                json.loads(fixture.read_text())
            except json.JSONDecodeError as e:
                pytest.fail(f"Invalid JSON in {fixture}: {e}")


class TestHeisenbergOnRealWorld:
    """Test Heisenberg parser and analyzer on real-world reports."""

    @pytest.fixture
    def fixture_paths(self) -> list[Path]:
        """Get all fixture paths, skip if none exist."""
        paths = get_all_fixture_paths()
        if not paths:
            pytest.skip("No real-world fixtures available yet")
        return paths

    def test_parser_handles_all_fixtures(self, fixture_paths: list[Path]):
        """Parser should successfully parse all real-world fixtures."""
        for fixture_path in fixture_paths:
            try:
                report = parse_playwright_report(fixture_path)
                assert report is not None, f"Parser returned None for {fixture_path}"
            except Exception as e:
                pytest.fail(f"Parser failed on {fixture_path}: {e}")

    def test_parser_extracts_failed_tests(self, fixture_paths: list[Path]):
        """Parser should extract failed tests from fixtures with failures."""
        fixtures_with_failures = 0

        for fixture_path in fixture_paths:
            report = parse_playwright_report(fixture_path)
            if report.has_failures:
                fixtures_with_failures += 1
                assert len(report.failed_tests) > 0, (
                    f"Report {fixture_path} has_failures=True but no failed_tests"
                )

        assert fixtures_with_failures > 0, (
            "Expected at least one fixture with failures"
        )

    def test_no_crash_on_any_fixture(self, fixture_paths: list[Path]):
        """Heisenberg should not crash on any real-world fixture."""
        for fixture_path in fixture_paths:
            try:
                report = parse_playwright_report(fixture_path)
                # Access all properties to ensure no lazy evaluation crashes
                _ = report.has_failures
                _ = report.summary
                _ = report.total_passed
                _ = report.total_failed
                for test in report.failed_tests:
                    _ = test.full_name
                    _ = test.error_summary
                    _ = test.file
                    _ = test.status
            except Exception as e:
                pytest.fail(f"Crash on {fixture_path}: {e}")


class TestFailureTypeDetection:
    """Test that Heisenberg correctly identifies different failure types."""

    def _get_fixture_for_type(self, failure_type: str) -> Path | None:
        """Find a fixture containing the specified failure type."""
        for fixture in get_all_fixture_paths():
            if failure_type in fixture.stem.lower():
                return fixture
        return None

    def test_detects_timeout_failure(self):
        """Should correctly identify timeout failures."""
        fixture = self._get_fixture_for_type("timeout")
        if fixture is None:
            pytest.skip("No timeout fixture available")

        report = parse_playwright_report(fixture)
        assert report.has_failures

        # At least one test should have timeout-related error
        timeout_found = False
        for test in report.failed_tests:
            if test.status == "timedOut" or "timeout" in test.error_summary.lower():
                timeout_found = True
                break

        assert timeout_found, "Expected to find timeout failure in timeout fixture"

    def test_detects_selector_failure(self):
        """Should correctly identify selector/locator failures."""
        fixture = self._get_fixture_for_type("selector")
        if fixture is None:
            pytest.skip("No selector fixture available")

        report = parse_playwright_report(fixture)
        assert report.has_failures

        # At least one test should have selector-related error
        selector_found = False
        selector_keywords = ["locator", "selector", "getby", "element", "not found", "visible"]
        for test in report.failed_tests:
            error_lower = test.error_summary.lower()
            if any(kw in error_lower for kw in selector_keywords):
                selector_found = True
                break

        assert selector_found, "Expected to find selector failure in selector fixture"

    def test_detects_assertion_failure(self):
        """Should correctly identify assertion failures."""
        fixture = self._get_fixture_for_type("assertion")
        if fixture is None:
            pytest.skip("No assertion fixture available")

        report = parse_playwright_report(fixture)
        assert report.has_failures

        # At least one test should have assertion-related error
        assertion_found = False
        assertion_keywords = ["expect", "assert", "expected", "received", "tobehave", "toequal"]
        for test in report.failed_tests:
            error_lower = test.error_summary.lower()
            if any(kw in error_lower for kw in assertion_keywords):
                assertion_found = True
                break

        assert assertion_found, "Expected to find assertion failure in assertion fixture"

    def test_detects_network_failure(self):
        """Should correctly identify network/API failures."""
        fixture = self._get_fixture_for_type("network")
        if fixture is None:
            pytest.skip("No network fixture available")

        report = parse_playwright_report(fixture)
        assert report.has_failures

        # At least one test should have network-related error
        network_found = False
        network_keywords = ["network", "api", "fetch", "request", "response", "500", "502", "503", "connection"]
        for test in report.failed_tests:
            error_lower = test.error_summary.lower()
            if any(kw in error_lower for kw in network_keywords):
                network_found = True
                break

        assert network_found, "Expected to find network failure in network fixture"

    def test_detects_flaky_pattern(self):
        """Should correctly identify flaky test patterns."""
        fixture = self._get_fixture_for_type("flaky")
        if fixture is None:
            pytest.skip("No flaky fixture available")

        report = parse_playwright_report(fixture)

        # Flaky tests might pass on retry, check stats or retry count
        flaky_found = report.total_flaky > 0

        if not flaky_found:
            # Alternative: check for retry patterns in failed tests
            for test in report.failed_tests:
                if hasattr(test, "retry_count") and test.retry_count > 0:
                    flaky_found = True
                    break

        assert flaky_found, "Expected to find flaky pattern in flaky fixture"


class TestFixtureQuality:
    """Validate the quality and completeness of fixtures."""

    def test_fixtures_have_realistic_structure(self):
        """Fixtures should have realistic Playwright report structure."""
        fixtures = get_all_fixture_paths()
        if not fixtures:
            pytest.skip("No fixtures available")

        required_keys = ["suites", "stats"]

        for fixture in fixtures:
            data = json.loads(fixture.read_text())
            for key in required_keys:
                assert key in data, f"Fixture {fixture} missing required key: {key}"

    def test_fixtures_have_meaningful_errors(self):
        """Failed tests in fixtures should have meaningful error messages."""
        fixtures = get_all_fixture_paths()
        if not fixtures:
            pytest.skip("No fixtures available")

        for fixture in fixtures:
            report = parse_playwright_report(fixture)
            for test in report.failed_tests:
                assert len(test.errors) > 0, (
                    f"Failed test in {fixture} has no errors"
                )
                assert len(test.errors[0].message) > 10, (
                    f"Error message in {fixture} is too short to be meaningful"
                )

    def test_each_project_has_at_least_one_fixture(self):
        """Each project directory should contain at least one fixture."""
        projects = get_project_directories()
        if not projects:
            pytest.skip("No project directories")

        for project in projects:
            fixtures = list(project.glob("*.json"))
            assert len(fixtures) > 0, (
                f"Project {project.name} has no JSON fixtures"
            )
