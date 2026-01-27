"""Pytest configuration for integration tests.

Integration tests in this directory require external services:
- LLM API keys (ANTHROPIC_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY)
- Database (DATABASE_URL)
- GitHub API (GITHUB_TOKEN)

Run integration tests with:
    pytest tests/integration/ --run-integration

Or run specific test files:
    pytest tests/integration/test_llm_integration.py --run-integration
"""

from __future__ import annotations

import pytest

# Mark all tests in this directory as integration tests
pytestmark = pytest.mark.integration
