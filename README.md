# The Heisenberg

[![CI](https://github.com/kamilpajak/heisenberg/actions/workflows/ci.yml/badge.svg)](https://github.com/kamilpajak/heisenberg/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/kamilpajak/heisenberg/branch/main/graph/badge.svg)](https://codecov.io/gh/kamilpajak/heisenberg)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**AI Root Cause Analysis for Flaky Tests**

> "I am the one who diagnoses." - Heisenberg

## Overview

Heisenberg is a GitHub Action that automatically diagnoses why your E2E tests failed by correlating Playwright traces with backend logs and using AI to identify the root cause.

**The Problem:** Flaky tests are a plague. They waste developer time, erode trust in CI/CD, and are notoriously hard to debug. Finding the root cause often requires correlating frontend errors with backend logs across multiple services.

**The Solution:** Heisenberg automates this forensic analysis. It collects all the evidence, correlates events by timestamp, and uses Claude AI to provide an intelligent diagnosis right in your PR.

## Features

- **Playwright Report Parsing** - Extracts failed tests, error messages, and stack traces from JSON reports
- **Docker Log Collection** - Gathers logs from backend services around the time of failure
- **Timeline Correlation** - Aligns frontend errors with backend events
- **AI-Powered Diagnosis** - Uses Claude to analyze all evidence and identify root causes
- **GitHub PR Integration** - Posts formatted analysis as PR comments
- **Confidence Scoring** - AI rates its confidence in each diagnosis
- **Log Compression** - Smart filtering to optimize token usage and costs

## Quick Start

Get started in under 5 minutes:

### 1. Add the Action to Your Workflow

Create or update `.github/workflows/e2e-tests.yml`:

```yaml
name: E2E Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Start backend services
        run: docker-compose up -d

      - name: Run Playwright tests
        run: npx playwright test --reporter=json
        continue-on-error: true

      - name: Analyze test failures
        if: failure()
        uses: kamilpajak/heisenberg@v1
        with:
          playwright-report: test-results/report.json
          docker-services: api,database,redis
          ai-analysis: true
          anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
```

### 2. Set Up Secrets

Add your Anthropic API key to repository secrets:
- Go to Settings > Secrets and variables > Actions
- Click "New repository secret"
- Name: `ANTHROPIC_API_KEY`
- Value: Your Claude API key

### 3. Run Your Tests

Push a commit or open a PR. When tests fail, Heisenberg will post a diagnosis comment.

## Installation

### As a GitHub Action (Recommended)

```yaml
- uses: kamilpajak/heisenberg@v1
  with:
    playwright-report: test-results/report.json
```

### As a CLI Tool

```bash
# Install with pip
pip install heisenberg

# Or with uv
uv pip install heisenberg

# Run analysis
heisenberg analyze --report test-results/report.json --ai-analysis
```

## Usage

### Basic Usage (Without AI)

```yaml
- uses: kamilpajak/heisenberg@v1
  with:
    playwright-report: test-results/report.json
```

This will parse failures and post a structured report without AI analysis.

### With AI Analysis

```yaml
- uses: kamilpajak/heisenberg@v1
  with:
    playwright-report: test-results/report.json
    ai-analysis: true
    anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
```

### With Docker Log Collection

```yaml
- uses: kamilpajak/heisenberg@v1
  with:
    playwright-report: test-results/report.json
    docker-services: api,postgres,redis
    log-window-seconds: 60
    ai-analysis: true
    anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
```

### CLI Usage

```bash
# Basic analysis
heisenberg analyze --report report.json

# With AI
heisenberg analyze --report report.json --ai-analysis

# With Docker logs
heisenberg analyze --report report.json --docker-services api,db --ai-analysis

# Output as JSON
heisenberg analyze --report report.json --output-format json
```

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `playwright-report` | Path to Playwright JSON report | Yes | `test-results/report.json` |
| `github-token` | GitHub token for PR comments | Yes | `${{ github.token }}` |
| `docker-services` | Comma-separated Docker service names | No | `""` |
| `log-window-seconds` | Time window for log collection | No | `30` |
| `ai-analysis` | Enable AI-powered analysis | No | `false` |
| `anthropic-api-key` | Anthropic API key (required if ai-analysis is true) | No | `""` |

## Outputs

| Output | Description |
|--------|-------------|
| `comment-id` | ID of the posted PR comment |
| `failed-tests-count` | Number of failed tests found |
| `analysis-summary` | Brief summary of the analysis |

## Example Output

When a test fails, Heisenberg posts a comment like this:

```markdown
## Test Failure Analysis

### Summary
- Total tests: 45
- Passed: 42
- Failed: 2
- Skipped: 1

### Failed Test: Login flow should redirect to dashboard

**Error:** `TimeoutError: locator.click: Timeout 30000ms exceeded`

**AI Diagnosis:**

## Root Cause Analysis
The test failure is caused by a database connection timeout in the authentication
service. The backend logs show the PostgreSQL connection pool was exhausted at
10:23:45, exactly when the login request was made.

## Evidence
- Backend log: "ERROR: connection pool exhausted" at 10:23:45
- Test timeout occurred at 10:23:47 (2 seconds later)
- Database container shows high connection count (100/100)

## Suggested Fix
Increase the PostgreSQL connection pool size in your docker-compose.yml or
investigate why connections are not being released properly.

## Confidence Score
HIGH (85%) - Strong correlation between database errors and test failure timing.
```

## How It Works

1. **Parse** - Heisenberg reads your Playwright JSON report and extracts all failed tests
2. **Collect** - If configured, it gathers Docker logs from your backend services
3. **Correlate** - Events are aligned by timestamp to build a timeline
4. **Analyze** - Claude AI examines all evidence to identify the root cause
5. **Report** - A formatted analysis is posted as a PR comment

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup

```bash
# Clone the repository
git clone https://github.com/kamilpajak/heisenberg.git
cd heisenberg

# Create virtual environment
uv venv && source .venv/bin/activate

# Install dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Run linter
ruff check src tests
```

## License

MIT - see [LICENSE](LICENSE) for details.

## Roadmap

- [ ] Support for more test frameworks (Jest, Cypress, Selenium)
- [ ] OpenAI GPT-4 support as alternative to Claude
- [ ] Historical analysis dashboard
- [ ] Pattern detection across multiple failures
- [ ] Slack/Discord notifications
