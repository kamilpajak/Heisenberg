"""Test scenarios for AI prompt tuning and validation.

These scenarios represent common flaky test patterns to ensure
the AI analysis produces useful, accurate diagnoses.
"""

from datetime import UTC, datetime, timedelta

import pytest

from heisenberg.core.diagnosis import ConfidenceLevel, parse_diagnosis
from heisenberg.core.models import PlaywrightTransformer
from heisenberg.integrations.docker import ContainerLogs, LogEntry
from heisenberg.llm.prompts import build_unified_prompt, get_system_prompt
from heisenberg.parsers.playwright import ErrorDetail, FailedTest, PlaywrightReport


class TestDatabaseTimeoutScenario:
    """Scenario: Test fails due to database connection timeout."""

    @pytest.fixture
    def scenario(self) -> tuple[PlaywrightReport, dict[str, ContainerLogs]]:
        """Database timeout scenario data."""
        report = PlaywrightReport(
            total_passed=9,
            total_failed=1,
            total_skipped=0,
            total_flaky=0,
            failed_tests=[
                FailedTest(
                    title="should create new user account",
                    file="tests/e2e/auth/signup.spec.ts",
                    suite="User Registration",
                    project="chromium",
                    status="failed",
                    duration_ms=35000,
                    start_time=datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
                    errors=[
                        ErrorDetail(
                            message="TimeoutError: locator.click: Timeout 30000ms exceeded.\n"
                            "Call log:\n"
                            "  - waiting for locator('[data-testid=\"submit-btn\"]')\n"
                            "  - locator resolved to <button>Submit</button>\n"
                            "  - attempting click action",
                            stack="Error: TimeoutError\n"
                            "    at signup.spec.ts:45:15\n"
                            "    at test.step (signup.spec.ts:40:5)",
                        )
                    ],
                    trace_path="test-results/signup/trace.zip",
                )
            ],
        )

        base_time = datetime(2024, 1, 15, 10, 29, 50, tzinfo=UTC)
        logs = {
            "api": ContainerLogs(
                container_name="api",
                entries=[
                    LogEntry(base_time, "POST /api/v1/users - started", "stdout"),
                    LogEntry(
                        base_time + timedelta(seconds=2),
                        "Attempting database connection...",
                        "stdout",
                    ),
                    LogEntry(
                        base_time + timedelta(seconds=5),
                        "WARN: Database connection pool exhausted",
                        "stderr",
                    ),
                    LogEntry(
                        base_time + timedelta(seconds=10),
                        "ERROR: Connection timeout after 10000ms",
                        "stderr",
                    ),
                    LogEntry(
                        base_time + timedelta(seconds=10),
                        "ERROR: Failed to create user: database unavailable",
                        "stderr",
                    ),
                    LogEntry(
                        base_time + timedelta(seconds=11),
                        "POST /api/v1/users - 503 Service Unavailable",
                        "stdout",
                    ),
                ],
            ),
            "postgres": ContainerLogs(
                container_name="postgres",
                entries=[
                    LogEntry(
                        base_time + timedelta(seconds=3),
                        "LOG: max_connections (100) reached",
                        "stderr",
                    ),
                    LogEntry(
                        base_time + timedelta(seconds=4),
                        'FATAL: too many connections for role "app"',
                        "stderr",
                    ),
                ],
            ),
        }

        return report, logs

    def test_prompt_includes_relevant_context(self, scenario):
        """Prompt should include all relevant failure context."""
        report, logs = scenario
        unified_run = PlaywrightTransformer.transform_report(report)
        _, prompt = build_unified_prompt(unified_run, container_logs=logs)

        # Should include test info
        assert "User Registration" in prompt
        assert "signup.spec.ts" in prompt
        assert "TimeoutError" in prompt

        # Should include backend context
        assert "database" in prompt.lower() or "postgres" in prompt.lower()
        assert "connection" in prompt.lower()

    def test_diagnosis_identifies_database_issue(self, scenario):
        """AI should identify database as root cause."""
        # This test validates the expected diagnosis structure
        # In real usage, this would validate actual AI output
        sample_ai_response = """## Root Cause Analysis
The test failure is caused by database connection pool exhaustion.
The PostgreSQL server reached its maximum connection limit.

## Evidence
- API logs show "Database connection pool exhausted"
- PostgreSQL logs show "max_connections (100) reached"
- The test timed out waiting for the submit button to respond

## Suggested Fix
1. Increase PostgreSQL max_connections
2. Implement connection pooling with PgBouncer
3. Add retry logic with exponential backoff

## Confidence Score
HIGH (>80%)
Clear correlation between database errors and test timeout."""

        diagnosis = parse_diagnosis(sample_ai_response)
        assert diagnosis.confidence == ConfidenceLevel.HIGH
        assert "database" in diagnosis.root_cause.lower()


class TestNetworkLatencyScenario:
    """Scenario: Test fails due to network latency/flakiness."""

    @pytest.fixture
    def scenario(self) -> tuple[PlaywrightReport, dict[str, ContainerLogs]]:
        """Network latency scenario data."""
        report = PlaywrightReport(
            total_passed=15,
            total_failed=1,
            total_skipped=0,
            total_flaky=0,
            failed_tests=[
                FailedTest(
                    title="should load dashboard with real-time data",
                    file="tests/e2e/dashboard/realtime.spec.ts",
                    suite="Dashboard",
                    project="chromium",
                    status="failed",
                    duration_ms=62000,
                    start_time=datetime(2024, 1, 15, 14, 20, 0, tzinfo=UTC),
                    errors=[
                        ErrorDetail(
                            message="expect(locator).toBeVisible(): Timeout 60000ms exceeded.\n"
                            "Locator: getByTestId('realtime-widget')\n"
                            "Expected: visible\n"
                            "Received: <element is not attached to DOM>",
                            stack="Error: expect(locator).toBeVisible\n"
                            "    at realtime.spec.ts:28:35",
                        )
                    ],
                )
            ],
        )

        base_time = datetime(2024, 1, 15, 14, 19, 55, tzinfo=UTC)
        logs = {
            "api": ContainerLogs(
                container_name="api",
                entries=[
                    LogEntry(base_time, "WebSocket connection established", "stdout"),
                    LogEntry(
                        base_time + timedelta(seconds=5),
                        "Subscribing to realtime channel: dashboard",
                        "stdout",
                    ),
                    LogEntry(
                        base_time + timedelta(seconds=30),
                        "WARN: WebSocket message delivery delayed by 25000ms",
                        "stderr",
                    ),
                    LogEntry(
                        base_time + timedelta(seconds=45),
                        "ERROR: WebSocket connection dropped - reconnecting",
                        "stderr",
                    ),
                    LogEntry(
                        base_time + timedelta(seconds=50),
                        "WebSocket reconnected after 5 attempts",
                        "stdout",
                    ),
                ],
            ),
        }

        return report, logs

    def test_prompt_includes_timing_info(self, scenario):
        """Prompt should include timing information."""
        report, logs = scenario
        unified_run = PlaywrightTransformer.transform_report(report)
        _, prompt = build_unified_prompt(unified_run, container_logs=logs)

        assert "62000" in prompt or "60000" in prompt  # Timeout values
        assert "WebSocket" in prompt


class TestRaceConditionScenario:
    """Scenario: Test fails due to race condition."""

    @pytest.fixture
    def scenario(self) -> tuple[PlaywrightReport, dict[str, ContainerLogs]]:
        """Race condition scenario data."""
        report = PlaywrightReport(
            total_passed=20,
            total_failed=1,
            total_skipped=0,
            total_flaky=0,
            failed_tests=[
                FailedTest(
                    title="should update cart total after adding item",
                    file="tests/e2e/cart/add-item.spec.ts",
                    suite="Shopping Cart",
                    project="chromium",
                    status="failed",
                    duration_ms=8500,
                    start_time=datetime(2024, 1, 15, 16, 45, 0, tzinfo=UTC),
                    errors=[
                        ErrorDetail(
                            message="expect(received).toBe(expected)\n"
                            "Expected: '$129.99'\n"
                            "Received: '$0.00'",
                            stack="Error: expect(received).toBe(expected)\n"
                            "    at add-item.spec.ts:52:25",
                        )
                    ],
                )
            ],
        )

        base_time = datetime(2024, 1, 15, 16, 44, 58, tzinfo=UTC)
        logs = {
            "api": ContainerLogs(
                container_name="api",
                entries=[
                    LogEntry(base_time, "POST /api/cart/items - started", "stdout"),
                    LogEntry(
                        base_time + timedelta(milliseconds=50),
                        "Adding item to cart: SKU-12345",
                        "stdout",
                    ),
                    LogEntry(
                        base_time + timedelta(milliseconds=100),
                        "Cart updated successfully",
                        "stdout",
                    ),
                    LogEntry(
                        base_time + timedelta(milliseconds=80),
                        "GET /api/cart/total - returning cached value",
                        "stdout",
                    ),
                    LogEntry(
                        base_time + timedelta(milliseconds=120),
                        "Cache invalidated for cart total",
                        "stdout",
                    ),
                ],
            ),
        }

        return report, logs

    def test_prompt_shows_timing_mismatch(self, scenario):
        """Prompt should show events that indicate race condition."""
        report, logs = scenario
        unified_run = PlaywrightTransformer.transform_report(report)
        _, prompt = build_unified_prompt(unified_run, container_logs=logs)

        assert "cart" in prompt.lower()
        assert "cache" in prompt.lower()


class TestAuthenticationFailureScenario:
    """Scenario: Test fails due to authentication/session issue."""

    @pytest.fixture
    def scenario(self) -> tuple[PlaywrightReport, dict[str, ContainerLogs]]:
        """Authentication failure scenario data."""
        report = PlaywrightReport(
            total_passed=12,
            total_failed=1,
            total_skipped=0,
            total_flaky=0,
            failed_tests=[
                FailedTest(
                    title="should access protected resource after login",
                    file="tests/e2e/auth/protected-route.spec.ts",
                    suite="Authentication",
                    project="firefox",
                    status="failed",
                    duration_ms=5200,
                    start_time=datetime(2024, 1, 15, 11, 15, 0, tzinfo=UTC),
                    errors=[
                        ErrorDetail(
                            message="expect(page).toHaveURL(): Page URL expected to match\n"
                            "Expected pattern: /dashboard\n"
                            "Received: /login?redirect=/dashboard",
                            stack="Error: expect(page).toHaveURL\n"
                            "    at protected-route.spec.ts:35:18",
                        )
                    ],
                )
            ],
        )

        base_time = datetime(2024, 1, 15, 11, 14, 58, tzinfo=UTC)
        logs = {
            "api": ContainerLogs(
                container_name="api",
                entries=[
                    LogEntry(base_time, "POST /api/auth/login - 200 OK", "stdout"),
                    LogEntry(
                        base_time + timedelta(seconds=1),
                        "Session created: sess_abc123",
                        "stdout",
                    ),
                    LogEntry(
                        base_time + timedelta(seconds=2),
                        "GET /api/dashboard - checking auth",
                        "stdout",
                    ),
                    LogEntry(
                        base_time + timedelta(seconds=2),
                        "WARN: Session not found in request headers",
                        "stderr",
                    ),
                    LogEntry(
                        base_time + timedelta(seconds=2),
                        "GET /api/dashboard - 401 Unauthorized",
                        "stdout",
                    ),
                ],
            ),
        }

        return report, logs

    def test_prompt_includes_auth_context(self, scenario):
        """Prompt should include authentication context."""
        report, logs = scenario
        unified_run = PlaywrightTransformer.transform_report(report)
        _, prompt = build_unified_prompt(unified_run, container_logs=logs)

        assert "login" in prompt.lower()
        assert "session" in prompt.lower() or "auth" in prompt.lower()


class TestElementNotFoundScenario:
    """Scenario: Test fails because element selector changed."""

    @pytest.fixture
    def scenario(self) -> tuple[PlaywrightReport, dict[str, ContainerLogs]]:
        """Element not found scenario data."""
        report = PlaywrightReport(
            total_passed=25,
            total_failed=1,
            total_skipped=0,
            total_flaky=0,
            failed_tests=[
                FailedTest(
                    title="should click the submit button",
                    file="tests/e2e/forms/contact.spec.ts",
                    suite="Contact Form",
                    project="webkit",
                    status="failed",
                    duration_ms=30500,
                    start_time=datetime(2024, 1, 15, 9, 0, 0, tzinfo=UTC),
                    errors=[
                        ErrorDetail(
                            message="locator.click: Timeout 30000ms exceeded.\n"
                            "Call log:\n"
                            "  - waiting for locator('button.submit-btn')\n"
                            "  - locator resolved to 0 elements",
                            stack="Error: locator.click\n    at contact.spec.ts:22:30",
                        )
                    ],
                )
            ],
        )

        # No backend errors - this is a frontend/selector issue
        logs = {
            "api": ContainerLogs(
                container_name="api",
                entries=[
                    LogEntry(
                        datetime(2024, 1, 15, 9, 0, 0, tzinfo=UTC),
                        "GET /contact - 200 OK",
                        "stdout",
                    ),
                ],
            ),
        }

        return report, logs

    def test_prompt_shows_selector_issue(self, scenario):
        """Prompt should indicate selector/element issue."""
        report, logs = scenario
        unified_run = PlaywrightTransformer.transform_report(report)
        _, prompt = build_unified_prompt(unified_run, container_logs=logs)

        assert "locator" in prompt.lower()
        assert "0 elements" in prompt or "resolved to 0" in prompt


class TestAPIErrorScenario:
    """Scenario: Test fails due to API returning error response."""

    @pytest.fixture
    def scenario(self) -> tuple[PlaywrightReport, dict[str, ContainerLogs]]:
        """API error scenario data."""
        report = PlaywrightReport(
            total_passed=18,
            total_failed=1,
            total_skipped=0,
            total_flaky=0,
            failed_tests=[
                FailedTest(
                    title="should display order confirmation",
                    file="tests/e2e/checkout/confirmation.spec.ts",
                    suite="Checkout",
                    project="chromium",
                    status="failed",
                    duration_ms=12000,
                    start_time=datetime(2024, 1, 15, 13, 30, 0, tzinfo=UTC),
                    errors=[
                        ErrorDetail(
                            message="expect(locator).toContainText(): Locator expected to contain text\n"
                            "Expected substring: 'Order confirmed'\n"
                            "Received: 'Something went wrong. Please try again.'",
                            stack="Error: expect(locator).toContainText\n"
                            "    at confirmation.spec.ts:48:22",
                        )
                    ],
                )
            ],
        )

        base_time = datetime(2024, 1, 15, 13, 29, 55, tzinfo=UTC)
        logs = {
            "api": ContainerLogs(
                container_name="api",
                entries=[
                    LogEntry(base_time, "POST /api/orders - started", "stdout"),
                    LogEntry(
                        base_time + timedelta(seconds=1),
                        "Processing order for user: user_123",
                        "stdout",
                    ),
                    LogEntry(
                        base_time + timedelta(seconds=2),
                        "Calling payment gateway...",
                        "stdout",
                    ),
                    LogEntry(
                        base_time + timedelta(seconds=5),
                        "ERROR: Payment gateway returned 500: internal error",
                        "stderr",
                    ),
                    LogEntry(
                        base_time + timedelta(seconds=5),
                        "POST /api/orders - 500 Internal Server Error",
                        "stdout",
                    ),
                ],
            ),
            "payment-service": ContainerLogs(
                container_name="payment-service",
                entries=[
                    LogEntry(
                        base_time + timedelta(seconds=3),
                        "Processing payment request",
                        "stdout",
                    ),
                    LogEntry(
                        base_time + timedelta(seconds=4),
                        "ERROR: Stripe API key invalid or expired",
                        "stderr",
                    ),
                ],
            ),
        }

        return report, logs

    def test_prompt_includes_api_error(self, scenario):
        """Prompt should include API error details."""
        report, logs = scenario
        unified_run = PlaywrightTransformer.transform_report(report)
        _, prompt = build_unified_prompt(unified_run, container_logs=logs)

        assert "500" in prompt or "error" in prompt.lower()
        assert "payment" in prompt.lower()


class TestResourceExhaustionScenario:
    """Scenario: Test fails due to resource exhaustion (memory/CPU)."""

    @pytest.fixture
    def scenario(self) -> tuple[PlaywrightReport, dict[str, ContainerLogs]]:
        """Resource exhaustion scenario data."""
        report = PlaywrightReport(
            total_passed=30,
            total_failed=1,
            total_skipped=0,
            total_flaky=0,
            failed_tests=[
                FailedTest(
                    title="should generate PDF report",
                    file="tests/e2e/reports/pdf-export.spec.ts",
                    suite="Report Export",
                    project="chromium",
                    status="failed",
                    duration_ms=120000,
                    start_time=datetime(2024, 1, 15, 15, 0, 0, tzinfo=UTC),
                    errors=[
                        ErrorDetail(
                            message="browserContext.newPage: Target page, context or browser has been closed",
                            stack="Error: browserContext.newPage\n    at pdf-export.spec.ts:15:40",
                        )
                    ],
                )
            ],
        )

        base_time = datetime(2024, 1, 15, 14, 59, 50, tzinfo=UTC)
        logs = {
            "api": ContainerLogs(
                container_name="api",
                entries=[
                    LogEntry(base_time, "POST /api/reports/pdf - started", "stdout"),
                    LogEntry(
                        base_time + timedelta(seconds=30),
                        "WARN: Memory usage at 85%",
                        "stderr",
                    ),
                    LogEntry(
                        base_time + timedelta(seconds=60),
                        "WARN: Memory usage at 95%",
                        "stderr",
                    ),
                    LogEntry(
                        base_time + timedelta(seconds=90),
                        "ERROR: Out of memory - killing process",
                        "stderr",
                    ),
                ],
            ),
        }

        return report, logs

    def test_prompt_shows_resource_issue(self, scenario):
        """Prompt should indicate resource exhaustion."""
        report, logs = scenario
        unified_run = PlaywrightTransformer.transform_report(report)
        _, prompt = build_unified_prompt(unified_run, container_logs=logs)

        assert "memory" in prompt.lower()
        assert "browser" in prompt.lower() or "closed" in prompt.lower()


class TestThirdPartyServiceScenario:
    """Scenario: Test fails due to third-party service unavailability."""

    @pytest.fixture
    def scenario(self) -> tuple[PlaywrightReport, dict[str, ContainerLogs]]:
        """Third-party service failure scenario data."""
        report = PlaywrightReport(
            total_passed=22,
            total_failed=1,
            total_skipped=0,
            total_flaky=0,
            failed_tests=[
                FailedTest(
                    title="should display Google Maps widget",
                    file="tests/e2e/location/map-widget.spec.ts",
                    suite="Location Services",
                    project="chromium",
                    status="failed",
                    duration_ms=45000,
                    start_time=datetime(2024, 1, 15, 17, 30, 0, tzinfo=UTC),
                    errors=[
                        ErrorDetail(
                            message="expect(locator).toBeVisible(): Timeout 30000ms exceeded.\n"
                            "Locator: getByTestId('google-map-canvas')\n"
                            "Expected: visible",
                            stack="Error: expect(locator).toBeVisible\n"
                            "    at map-widget.spec.ts:34:25",
                        )
                    ],
                )
            ],
        )

        base_time = datetime(2024, 1, 15, 17, 29, 55, tzinfo=UTC)
        logs = {
            "api": ContainerLogs(
                container_name="api",
                entries=[
                    LogEntry(
                        base_time,
                        "Loading Google Maps SDK",
                        "stdout",
                    ),
                    LogEntry(
                        base_time + timedelta(seconds=5),
                        "ERROR: Failed to load https://maps.googleapis.com/maps/api/js",
                        "stderr",
                    ),
                    LogEntry(
                        base_time + timedelta(seconds=5),
                        "Network error: ERR_CONNECTION_TIMED_OUT",
                        "stderr",
                    ),
                ],
            ),
        }

        return report, logs

    def test_prompt_includes_external_service(self, scenario):
        """Prompt should indicate external service issue."""
        report, logs = scenario
        unified_run = PlaywrightTransformer.transform_report(report)
        _, prompt = build_unified_prompt(unified_run, container_logs=logs)

        assert "google" in prompt.lower() or "maps" in prompt.lower()
        assert "network" in prompt.lower() or "timeout" in prompt.lower()


class TestConcurrencyScenario:
    """Scenario: Test fails due to concurrent test interference."""

    @pytest.fixture
    def scenario(self) -> tuple[PlaywrightReport, dict[str, ContainerLogs]]:
        """Concurrency interference scenario data."""
        report = PlaywrightReport(
            total_passed=40,
            total_failed=1,
            total_skipped=0,
            total_flaky=0,
            failed_tests=[
                FailedTest(
                    title="should have unique user email",
                    file="tests/e2e/user/profile.spec.ts",
                    suite="User Profile",
                    project="chromium",
                    status="failed",
                    duration_ms=3500,
                    start_time=datetime(2024, 1, 15, 18, 0, 0, tzinfo=UTC),
                    errors=[
                        ErrorDetail(
                            message="expect(received).toBe(expected)\n"
                            "Expected: 'test_user_abc@example.com'\n"
                            "Received: 'test_user_xyz@example.com'",
                            stack="Error: expect(received).toBe\n    at profile.spec.ts:28:30",
                        )
                    ],
                )
            ],
        )

        base_time = datetime(2024, 1, 15, 17, 59, 58, tzinfo=UTC)
        logs = {
            "api": ContainerLogs(
                container_name="api",
                entries=[
                    LogEntry(
                        base_time,
                        "GET /api/users/me - returning user test_user_abc",
                        "stdout",
                    ),
                    LogEntry(
                        base_time + timedelta(milliseconds=500),
                        "PUT /api/users/me - updating email for test_user_xyz",
                        "stdout",
                    ),
                    LogEntry(
                        base_time + timedelta(seconds=1),
                        "GET /api/users/me - returning user test_user_xyz",
                        "stdout",
                    ),
                ],
            ),
        }

        return report, logs

    def test_prompt_shows_data_conflict(self, scenario):
        """Prompt should show data mismatch indicating concurrency."""
        report, logs = scenario
        unified_run = PlaywrightTransformer.transform_report(report)
        _, prompt = build_unified_prompt(unified_run, container_logs=logs)

        assert "user" in prompt.lower()
        assert "abc" in prompt.lower() and "xyz" in prompt.lower()


class TestFlakySelectorScenario:
    """Scenario: Test fails intermittently due to dynamic content."""

    @pytest.fixture
    def scenario(self) -> tuple[PlaywrightReport, dict[str, ContainerLogs]]:
        """Flaky selector scenario data."""
        report = PlaywrightReport(
            total_passed=35,
            total_failed=1,
            total_skipped=0,
            total_flaky=0,
            failed_tests=[
                FailedTest(
                    title="should click notification banner",
                    file="tests/e2e/notifications/banner.spec.ts",
                    suite="Notifications",
                    project="chromium",
                    status="failed",
                    duration_ms=31000,
                    start_time=datetime(2024, 1, 15, 19, 15, 0, tzinfo=UTC),
                    errors=[
                        ErrorDetail(
                            message="locator.click: Timeout 30000ms exceeded.\n"
                            "Call log:\n"
                            "  - waiting for locator('div.notification:nth-child(1)')\n"
                            '  - locator resolved to <div class="notification">...</div>\n'
                            "  - element is not stable - waiting...\n"
                            "  - element is outside viewport - scrolling into view",
                            stack="Error: locator.click\n    at banner.spec.ts:18:35",
                        )
                    ],
                )
            ],
        )

        # No backend errors - this is a UI timing issue
        logs = {
            "api": ContainerLogs(
                container_name="api",
                entries=[
                    LogEntry(
                        datetime(2024, 1, 15, 19, 15, 0, tzinfo=UTC),
                        "GET /api/notifications - 200 OK (5 items)",
                        "stdout",
                    ),
                ],
            ),
        }

        return report, logs

    def test_prompt_shows_stability_issue(self, scenario):
        """Prompt should indicate element stability issue."""
        report, logs = scenario
        unified_run = PlaywrightTransformer.transform_report(report)
        _, prompt = build_unified_prompt(unified_run, container_logs=logs)

        assert "stable" in prompt.lower() or "viewport" in prompt.lower()
        assert "nth-child" in prompt.lower() or "notification" in prompt.lower()


class TestSystemPromptQuality:
    """Test the quality of the system prompt."""

    def test_system_prompt_is_comprehensive(self):
        """System prompt should cover all major failure categories."""
        prompt = get_system_prompt()

        # Should mention key analysis areas
        assert "timing" in prompt.lower()
        assert "backend" in prompt.lower() or "api" in prompt.lower()
        assert "frontend" in prompt.lower() or "element" in prompt.lower()
        assert "flaky" in prompt.lower()

        # Should request confidence score
        assert "confidence" in prompt.lower()

        # Should request evidence
        assert "evidence" in prompt.lower()

        # Should request actionable fix
        assert "fix" in prompt.lower() or "suggest" in prompt.lower()

    def test_system_prompt_defines_output_format(self):
        """System prompt should define clear output format."""
        prompt = get_system_prompt()

        # Should have section headers
        assert "Root Cause" in prompt
        assert "Evidence" in prompt
        assert "Suggested Fix" in prompt or "Fix" in prompt
        assert "Confidence" in prompt
