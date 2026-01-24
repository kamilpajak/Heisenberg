"""Pytest configuration and fixtures."""

import pytest


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
