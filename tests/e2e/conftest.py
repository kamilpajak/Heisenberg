"""Pytest configuration for end-to-end tests.

E2E tests in this directory require external services:
- LLM API keys (ANTHROPIC_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY)
- Database (DATABASE_URL)
- GitHub API (GITHUB_TOKEN)

Run e2e tests with:
    pytest tests/e2e/ --run-e2e

Or run specific test files:
    pytest tests/e2e/test_llm_integration.py --run-e2e
"""

from __future__ import annotations

import pytest

# Mark all tests in this directory as e2e tests
pytestmark = pytest.mark.e2e
