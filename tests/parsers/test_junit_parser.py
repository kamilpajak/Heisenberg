"""Tests for JUnit XML parser.

These tests verify that Heisenberg can parse JUnit XML reports
and convert them to the unified failure model.
"""

from __future__ import annotations

from heisenberg.core.models import Framework, UnifiedTestRun
from heisenberg.parsers.junit import JUnitParser


class TestJUnitParser:
    """Tests for JUnitParser class."""

    def test_parse_simple_report_with_failures(self):
        """Parse JUnit XML with failures."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <testsuites name="test suite" tests="3" failures="1" errors="0" time="5.0">
            <testsuite name="LoginTests" tests="3" failures="1" time="5.0">
                <testcase classname="LoginTests" name="test_login_success" time="1.0"/>
                <testcase classname="LoginTests" name="test_login_failure" time="2.0">
                    <failure message="Expected true but got false" type="AssertionError">
AssertionError: Expected true but got false
    at LoginTests.test_login_failure(LoginTests.java:42)
    at junit.framework.TestCase.runTest(TestCase.java:176)
                    </failure>
                </testcase>
                <testcase classname="LoginTests" name="test_logout" time="1.5"/>
            </testsuite>
        </testsuites>
        """

        report = JUnitParser.parse_string(xml)

        assert report.total_tests == 3
        assert report.total_passed == 2
        assert report.total_failed == 1
        assert len(report.failed_tests) == 1

        failure = report.failed_tests[0]
        assert failure.name == "test_login_failure"
        assert failure.classname == "LoginTests"
        assert "Expected true but got false" in failure.failure_message
        assert failure.failure_type == "AssertionError"

    def test_parse_report_with_errors(self):
        """Parse JUnit XML with errors (exceptions)."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <testsuites tests="2" failures="0" errors="1">
            <testsuite name="APITests" tests="2" errors="1">
                <testcase classname="APITests" name="test_connection" time="0.5">
                    <error message="Connection refused" type="ConnectionError">
ConnectionError: Connection refused
    at APITests.test_connection(APITests.java:15)
                    </error>
                </testcase>
                <testcase classname="APITests" name="test_ping" time="0.1"/>
            </testsuite>
        </testsuites>
        """

        report = JUnitParser.parse_string(xml)

        assert report.total_tests == 2
        assert report.total_errors == 1  # Errors are tracked separately in JUnit
        assert len(report.failed_tests) == 1  # But failed_tests includes both

        failure = report.failed_tests[0]
        assert failure.name == "test_connection"
        assert "Connection refused" in failure.failure_message

    def test_parse_report_with_skipped(self):
        """Parse JUnit XML with skipped tests."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <testsuites tests="3" failures="0" skipped="1">
            <testsuite name="FeatureTests" tests="3" skipped="1">
                <testcase classname="FeatureTests" name="test_feature_a" time="1.0"/>
                <testcase classname="FeatureTests" name="test_feature_b" time="0.0">
                    <skipped message="Feature not implemented"/>
                </testcase>
                <testcase classname="FeatureTests" name="test_feature_c" time="1.0"/>
            </testsuite>
        </testsuites>
        """

        report = JUnitParser.parse_string(xml)

        assert report.total_tests == 3
        assert report.total_passed == 2
        assert report.total_skipped == 1

    def test_parse_multiple_test_suites(self):
        """Parse JUnit XML with multiple test suites."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <testsuites tests="4" failures="2">
            <testsuite name="Suite1" tests="2" failures="1">
                <testcase classname="Suite1" name="test1" time="1.0">
                    <failure message="Error 1"/>
                </testcase>
                <testcase classname="Suite1" name="test2" time="1.0"/>
            </testsuite>
            <testsuite name="Suite2" tests="2" failures="1">
                <testcase classname="Suite2" name="test3" time="1.0"/>
                <testcase classname="Suite2" name="test4" time="1.0">
                    <failure message="Error 2"/>
                </testcase>
            </testsuite>
        </testsuites>
        """

        report = JUnitParser.parse_string(xml)

        assert report.total_tests == 4
        assert report.total_failed == 2
        assert len(report.failed_tests) == 2

    def test_parse_single_testsuite_root(self):
        """Parse JUnit XML with single testsuite as root."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <testsuite name="UnitTests" tests="2" failures="1">
            <testcase classname="UnitTests" name="test_pass" time="0.5"/>
            <testcase classname="UnitTests" name="test_fail" time="0.5">
                <failure message="Assertion failed"/>
            </testcase>
        </testsuite>
        """

        report = JUnitParser.parse_string(xml)

        assert report.total_tests == 2
        assert report.total_failed == 1

    def test_extract_file_from_classname(self):
        """Extract file path from Java-style classname."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <testsuite tests="1" failures="1">
            <testcase classname="com.example.tests.LoginTest" name="testLogin" time="1.0">
                <failure message="Failed"/>
            </testcase>
        </testsuite>
        """

        report = JUnitParser.parse_string(xml)
        failure = report.failed_tests[0]

        # Should extract file path from classname
        assert failure.file_path == "com/example/tests/LoginTest"


class TestJUnitToUnifiedConversion:
    """Tests for converting JUnit reports to unified model."""

    def test_convert_to_unified_model(self):
        """Convert JUnitReport to UnifiedTestRun."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <testsuites name="jest tests" tests="5" failures="2" skipped="1">
            <testsuite name="AuthTests" tests="5" failures="2" skipped="1">
                <testcase classname="AuthTests" name="login should work" time="1.0"/>
                <testcase classname="AuthTests" name="login should fail with bad password" time="0.5">
                    <failure message="Expected 401 but got 200" type="AssertionError">
AssertionError: Expected 401 but got 200
    at AuthTests.login(AuthTests.js:42)
                    </failure>
                </testcase>
                <testcase classname="AuthTests" name="logout should work" time="0.3"/>
                <testcase classname="AuthTests" name="session should expire" time="0.2">
                    <failure message="Timeout waiting for session"/>
                </testcase>
                <testcase classname="AuthTests" name="oauth flow" time="0.0">
                    <skipped message="OAuth not configured"/>
                </testcase>
            </testsuite>
        </testsuites>
        """

        report = JUnitParser.parse_string(xml)
        unified = JUnitParser.to_unified(
            report,
            run_id="junit-123",
            repository="test/repo",
        )

        assert isinstance(unified, UnifiedTestRun)
        assert unified.run_id == "junit-123"
        assert unified.repository == "test/repo"
        assert unified.total_tests == 5
        assert unified.passed_tests == 2
        assert unified.failed_tests == 2
        assert unified.skipped_tests == 1
        assert len(unified.failures) == 2

        # Check first failure
        f1 = unified.failures[0]
        assert f1.test_title == "login should fail with bad password"
        assert "Expected 401 but got 200" in f1.error.message
        assert f1.metadata.framework == Framework.JUNIT

    def test_unified_model_has_stack_trace(self):
        """Unified model should include stack trace from failure content."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <testsuite tests="1" failures="1">
            <testcase classname="Tests" name="testFail" time="1.0">
                <failure message="Assert failed" type="AssertionError">
java.lang.AssertionError: Assert failed
    at Tests.testFail(Tests.java:10)
    at sun.reflect.Method.invoke(Method.java:498)
                </failure>
            </testcase>
        </testsuite>
        """

        report = JUnitParser.parse_string(xml)
        unified = JUnitParser.to_unified(report)

        assert len(unified.failures) == 1
        failure = unified.failures[0]
        assert failure.error.stack_trace is not None
        assert "Tests.java:10" in failure.error.stack_trace


class TestJUnitParserEdgeCases:
    """Edge case tests for JUnit parser."""

    def test_empty_report(self):
        """Parse empty JUnit report."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <testsuites tests="0" failures="0"/>
        """

        report = JUnitParser.parse_string(xml)
        assert report.total_tests == 0
        assert report.total_failed == 0

    def test_parse_from_file(self, tmp_path):
        """Parse JUnit XML from file."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <testsuite tests="1" failures="1">
            <testcase classname="FileTest" name="test" time="1.0">
                <failure message="File error"/>
            </testcase>
        </testsuite>
        """

        file_path = tmp_path / "junit.xml"
        file_path.write_text(xml)

        report = JUnitParser.parse_file(file_path)

        assert report.total_tests == 1
        assert report.total_failed == 1

    def test_failure_without_message_attribute(self):
        """Handle failure element without message attribute."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <testsuite tests="1" failures="1">
            <testcase classname="Tests" name="test" time="1.0">
                <failure>Some error occurred here</failure>
            </testcase>
        </testsuite>
        """

        report = JUnitParser.parse_string(xml)

        assert report.total_failed == 1
        assert "Some error occurred" in report.failed_tests[0].failure_message

    def test_special_characters_in_names(self):
        """Handle special characters in test names."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <testsuite tests="1" failures="1">
            <testcase classname="Tests" name="test &apos;special&apos; &amp; &quot;chars&quot;" time="1.0">
                <failure message="Failed with &lt;value&gt;"/>
            </testcase>
        </testsuite>
        """

        report = JUnitParser.parse_string(xml)

        assert "special" in report.failed_tests[0].name
        assert "<value>" in report.failed_tests[0].failure_message
