# The Heisenberg

[![CI](https://github.com/kamilpajak/heisenberg/actions/workflows/ci.yml/badge.svg)](https://github.com/kamilpajak/heisenberg/actions/workflows/ci.yml)
[![Quality Gate](https://sonarcloud.io/api/project_badges/measure?project=kamilpajak_Heisenberg&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=kamilpajak_Heisenberg)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=kamilpajak_Heisenberg&metric=coverage)](https://sonarcloud.io/summary/new_code?id=kamilpajak_Heisenberg)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**AI Root Cause Analysis for E2E Test Failures**

*Instantly diagnose flaky tests and other CI errors.*

> "I am the one who diagnoses." - Heisenberg

## Overview

Heisenberg is a GitHub Action that automatically diagnoses why your E2E tests failed by correlating Playwright traces with backend logs and using AI to identify the root cause.

**The Problem:** CI failures waste engineering time. Flaky tests erode trust, but even consistent failures require tedious debugging - correlating frontend errors with backend logs across multiple services.

**The Solution:** Heisenberg automates this forensic analysis for *all* test failures. It collects all the evidence, correlates events by timestamp, and uses AI to provide an intelligent diagnosis right in your PR - whether it's a flaky test, a real bug, or an infrastructure issue.

## Features

- **Framework-Agnostic Analysis** - Unified model supports Playwright and JUnit (more frameworks planned)
- **Playwright Report Parsing** - Extracts failed tests, error messages, and stack traces from JSON reports
- **Docker Log Collection** - Gathers logs from backend services around the time of failure
- **Timeline Correlation** - Aligns frontend errors with backend events
- **AI-Powered Diagnosis** - Uses Claude, OpenAI, or Gemini to analyze all evidence and identify root causes
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
          playwright-report: test-results.json
          docker-services: api,database,redis
          ai-analysis: true
          google-api-key: ${{ secrets.GOOGLE_API_KEY }}
```

### 2. Set Up Secrets

Add your Google API key to repository secrets:
- Go to Settings > Secrets and variables > Actions
- Click "New repository secret"
- Name: `GOOGLE_API_KEY`
- Value: Your Google AI API key

### 3. Run Your Tests

Push a commit or open a PR. When tests fail, Heisenberg will post a diagnosis comment.

## Installation

### As a GitHub Action (Recommended)

```yaml
- uses: kamilpajak/heisenberg@v1
  with:
    playwright-report: test-results.json
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
    playwright-report: test-results.json
```

This will parse failures and post a structured report without AI analysis.

### With AI Analysis

```yaml
- uses: kamilpajak/heisenberg@v1
  with:
    playwright-report: test-results.json
    ai-analysis: true
    google-api-key: ${{ secrets.GOOGLE_API_KEY }}
```

### With Docker Log Collection

```yaml
- uses: kamilpajak/heisenberg@v1
  with:
    playwright-report: test-results.json
    docker-services: api,database,redis
    log-window-seconds: 60
    ai-analysis: true
    google-api-key: ${{ secrets.GOOGLE_API_KEY }}
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

### Fetching from GitHub Actions

Analyze reports directly from GitHub Actions workflow runs:

```bash
# Fetch and analyze the latest failed run
heisenberg fetch-github --repo owner/repo --ai-analysis

# Fetch a specific run
heisenberg fetch-github --repo owner/repo --run-id 1234567890

# Save report locally instead of analyzing
heisenberg fetch-github --repo owner/repo --output report.json

# Use a different LLM provider
heisenberg fetch-github --repo owner/repo --ai-analysis --provider openai

# List available artifacts (for debugging)
heisenberg fetch-github --repo owner/repo --list-artifacts

# Merge blob reports from sharded test runs (e.g., microsoft/playwright)
heisenberg fetch-github --repo microsoft/playwright --merge-blobs --artifact-name blob-report
```

> **Note:** The `--merge-blobs` flag requires Node.js and Playwright installed locally.
> It uses `npx playwright merge-reports` to combine sharded test results.

**Options:**

| Option | Description |
|--------|-------------|
| `--repo, -r` | Repository in `owner/repo` format (required) |
| `--token, -t` | GitHub token (or set `GITHUB_TOKEN` env) |
| `--run-id` | Specific workflow run ID (default: latest failed) |
| `--output, -o` | Save report to file instead of analyzing |
| `--artifact-name` | Artifact name pattern (default: `playwright`) |
| `--ai-analysis, -a` | Enable AI analysis |
| `--provider, -p` | LLM provider: `anthropic`, `openai`, `google` |
| `--list-artifacts` | List available artifacts for debugging |
| `--merge-blobs` | Merge Playwright blob reports (requires Node.js) |

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `playwright-report` | Path to Playwright JSON report | No | `test-results.json` |
| `github-token` | GitHub token for PR comments | No | `${{ github.token }}` |
| `docker-services` | Comma-separated Docker service names | No | `""` |
| `log-window-seconds` | Time window for log collection | No | `30` |
| `ai-analysis` | Enable AI-powered analysis | No | `false` |
| `ai-provider` | LLM provider: `anthropic`, `openai`, `google` | No | `google` |
| `anthropic-api-key` | Anthropic API key (for Claude) | No | `""` |
| `openai-api-key` | OpenAI API key (for GPT-4) | No | `""` |
| `google-api-key` | Google API key (for Gemini) | No | `""` |

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

## Privacy & Security

Heisenberg is designed with a **"Bring Your Own Key" (BYOK)** model. Your data stays between you and your chosen LLM provider.

### What Data Is Sent to the LLM?

When AI analysis is enabled, Heisenberg sends only the **minimum context needed** for diagnosis:

| Data Type | What's Sent | What's NOT Sent |
|-----------|-------------|-----------------|
| **Test Results** | Failed test names, error messages, stack traces | Passing tests, test source code |
| **Playwright Traces** | Console errors, failed network requests, action timeline | Screenshots (unless vision analysis enabled), full network payloads |
| **Docker Logs** | Logs within ±30s of failure, filtered for errors/warnings | Full container history, environment variables |
| **Job Logs** | Relevant error sections from CI output | Full workflow logs, secrets |

### Where Does the Data Go?

```
Your CI Environment → Heisenberg (processes locally) → LLM Provider API
                                                        ↓
                                              (Anthropic / OpenAI / Google)
```

- **Heisenberg does NOT store your data.** All processing happens in your CI runner or local machine.
- **Data goes directly to your chosen LLM provider** using YOUR API key.
- **No telemetry, no analytics, no phone-home.** The CLI/Action works fully offline (except for the LLM API call).

### LLM Provider Data Policies

Your data is subject to your LLM provider's policies:

| Provider | Data Retention | Training Opt-Out |
|----------|---------------|------------------|
| **Google (Gemini)** | [Paid API data not used for training](https://ai.google.dev/terms) | Default |
| **Anthropic (Claude)** | [API data not used for training](https://www.anthropic.com/policies/privacy-policy) | Default |
| **OpenAI** | [API data not used for training](https://openai.com/policies/api-data-usage-policies) | Default |

### Security Best Practices

1. **Use repository secrets** for API keys - never commit them to code
2. **Limit Docker services** to only those needed for debugging
3. **Review the log window** - default 30s is usually sufficient
4. **Use environment-specific keys** - separate keys for CI vs. local development

### For Enterprise / Regulated Environments

If your organization has strict data residency or compliance requirements:

- **Self-hosted LLM option** coming soon (Ollama, local Llama/Mistral)
- **On-premise deployment** available in Enterprise tier
- **Audit logs** for all AI analysis requests (Enterprise)

> **Questions about data handling?** Open an issue or start a [Discussion](https://github.com/kamilpajak/heisenberg/discussions).

## Cost Estimation

Heisenberg uses your own API keys, so you pay only for what you use. Here's what to expect:

### Typical Token Usage Per Analysis

*Based on real-world measurements:*

| Scenario | Input Tokens | Output Tokens | Total |
|----------|-------------|---------------|-------|
| **Small** (1-2 failures, no logs) | ~1,500 | ~400 | ~2,000 |
| **Medium** (3-5 failures) | ~3,000 | ~800 | ~4,000 |
| **Large** (10 failures)* | ~4,400 | ~1,300 | ~5,700 |
| **XL** (10+ failures, Docker logs) | ~8,000 | ~2,000 | ~10,000 |

*\*Measured on validation suite with 10 intentional failures*

### Cost Per Analysis by Provider

Based on measured "Large" scenario (~4,400 input + ~1,300 output tokens = 10 failures):

| Provider | Model | Input/1M | Output/1M | Cost per Analysis | Monthly (100 runs) |
|----------|-------|----------|-----------|-------------------|-------------------|
| **Anthropic** | Claude Sonnet 4* | $3.00 | $15.00 | ~$0.03 | ~$3 |
| **Anthropic** | Claude Haiku 4.5 | $1.00 | $5.00 | ~$0.01 | ~$1 |
| **OpenAI** | GPT-5 | $5.00 | $15.00 | ~$0.04 | ~$4 |
| **OpenAI** | GPT-5 mini | $0.40 | $1.60 | ~$0.004 | ~$0.40 |
| **Google** | Gemini 3 Pro Preview** | $2.00 | $12.00 | ~$0.025 | ~$2.50 |

*\*Default model for `--provider anthropic`*
*\*\*Default model for `--provider google` (default provider)*

### Cost Optimization Tips

1. **Start with budget models** - Claude Haiku 4.5 or GPT-5 mini are excellent for most failures
2. **Use Sonnet/GPT-5 for complex cases** - when budget models miss the root cause
3. **Filter Docker services** - only include services relevant to the failure
4. **Adjust log window** - default 30s is usually enough, reduce if logs are verbose

### Real-World Example

A team running 50 CI pipelines/day with ~10% failure rate:
- 5 failed runs/day × 30 days = **150 analyses/month**

| Model | Cost/month | Notes |
|-------|------------|-------|
| GPT-5 mini | ~$0.60 | Best value for OpenAI |
| Claude Haiku 4.5 | ~$1.50 | Fast, reliable |
| Gemini 3 Pro Preview | ~$3.75 | Default for Gemini |
| Claude Sonnet 4 | ~$4.50 | Default for Claude, excellent |
| GPT-5 | ~$6.00 | Top-tier OpenAI |

*Measured: 10 failures = ~5,700 tokens (~$0.03 with Sonnet)*

> **Note:** Prices based on January 2026 API rates. Check provider pricing pages for current rates:
> [Anthropic](https://www.anthropic.com/pricing) | [OpenAI](https://openai.com/api/pricing) | [Google](https://ai.google.dev/pricing)

## API Documentation

Heisenberg provides a REST API for programmatic access. See [docs/API.md](docs/API.md) for:

- Authentication with API keys
- Health check endpoints
- Analysis submission
- Feedback collection
- Usage tracking

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

- [x] OpenAI GPT-4 support as alternative to Claude
- [x] Google Gemini support
- [x] GitHub Actions artifact fetching (`fetch-github` command)
- [x] REST API backend with usage tracking
- [x] Playwright blob reports support (`--merge-blobs` for sharded tests)
- [ ] Support for more test frameworks (Jest, Cypress, Selenium)
- [ ] Historical analysis dashboard
- [ ] Pattern detection across multiple failures
- [ ] Kubernetes log collection
- [ ] Slack/Discord notifications
