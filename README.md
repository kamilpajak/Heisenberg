# The Heisenberg

AI Root Cause Analysis for Flaky Tests.

## Overview

Heisenberg is a GitHub Action that automatically diagnoses why your E2E tests failed by correlating Playwright traces with backend logs and infrastructure metrics.

## Installation

```yaml
- uses: kamilpajak/heisenberg@v1
  with:
    playwright-report: test-results/report.json
```

## Development

```bash
# Install dependencies
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

# Run tests
pytest

# Run linter
ruff check src tests
```

## License

MIT
