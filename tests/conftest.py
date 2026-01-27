"""Pytest configuration and fixtures.

Test Directory Structure
========================
tests/
├── conftest.py          # Shared fixtures and pytest configuration
├── factories.py         # Factory functions for test data
├── fixtures/            # Static test fixtures (JSON, XML, etc.)
├── integration/         # Integration tests (require external services)
│   ├── conftest.py      # Auto-marks all tests as @pytest.mark.integration
│   └── test_*.py        # Tests requiring API keys, DB, GitHub, etc.
└── test_*.py            # Unit tests (pure logic, mocks, no external deps)

Running Tests
=============
# Unit tests only (fast, no external dependencies)
pytest tests/ -x

# Include integration tests (requires API keys)
pytest tests/ --run-integration

# Include fuzz tests (slow, uses schemathesis)
pytest tests/ --run-fuzz

# Run only integration tests
pytest tests/integration/ --run-integration
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from tests.factories import (
    make_ai_analysis_result,
    make_container_logs,
    make_diagnosis,
    make_llm_analysis,
    make_playwright_report,
    make_unified_run,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from heisenberg.core.analyzer import AIAnalysisResult
    from heisenberg.core.diagnosis import Diagnosis
    from heisenberg.integrations.docker import ContainerLogs
    from heisenberg.llm.models import LLMAnalysis
    from heisenberg.parsers.playwright import PlaywrightReport


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests (requires API keys)",
    )
    parser.addoption(
        "--run-fuzz",
        action="store_true",
        default=False,
        help="Run fuzz tests (slower, uses schemathesis)",
    )


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests (require API keys)",
    )
    config.addinivalue_line(
        "markers",
        "fuzz: marks tests as fuzz tests (slower, uses schemathesis)",
    )


def pytest_collection_modifyitems(config, items):
    """Skip integration and fuzz tests unless explicitly enabled."""
    run_integration = config.getoption("--run-integration")
    run_fuzz = config.getoption("--run-fuzz")

    skip_integration = pytest.mark.skip(reason="need --run-integration option to run")
    skip_fuzz = pytest.mark.skip(reason="need --run-fuzz option to run")

    for item in items:
        if "integration" in item.keywords and not run_integration:
            item.add_marker(skip_integration)
        if "fuzz" in item.keywords and not run_fuzz:
            item.add_marker(skip_fuzz)


@pytest.fixture(scope="session")
def database_url() -> str | None:
    """Get database URL from environment."""
    return os.environ.get("DATABASE_URL")


@pytest.fixture(scope="session")
def setup_test_database(
    request: pytest.FixtureRequest, database_url: str | None
) -> Generator[None, None, None]:
    """
    Apply database migrations for integration tests.

    This fixture mirrors production deployment by running Alembic migrations.
    Note: Database connection initialization is left to the app lifespan
    to avoid event loop conflicts with async test runners.

    Only activates when:
    - DATABASE_URL is set
    - Running integration tests
    """
    run_integration = request.config.getoption("--run-integration", default=False)

    # Skip if not running integration tests or no DATABASE_URL
    if not run_integration or not database_url:
        yield
        return

    # Run Alembic migrations (mirrors production deployment)
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")

    yield


# =============================================================================
# Shared Test Fixtures
# =============================================================================
# These fixtures use factories from tests/factories.py.
# Prefer using these over defining local fixtures in test files.


@pytest.fixture
def sample_llm_analysis() -> LLMAnalysis:
    """Sample LLMAnalysis for testing."""
    return make_llm_analysis()


@pytest.fixture
def sample_report() -> PlaywrightReport:
    """Sample PlaywrightReport with one failed test."""
    return make_playwright_report()


@pytest.fixture
def sample_logs() -> dict[str, ContainerLogs]:
    """Sample container logs for testing."""
    return {"api": make_container_logs()}


@pytest.fixture
def sample_diagnosis() -> Diagnosis:
    """Sample Diagnosis for testing."""
    return make_diagnosis()


@pytest.fixture
def sample_unified_run():
    """Sample UnifiedTestRun for testing."""
    return make_unified_run()


@pytest.fixture
def sample_result() -> AIAnalysisResult:
    """Sample AIAnalysisResult for testing."""
    return make_ai_analysis_result()
