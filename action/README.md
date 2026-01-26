# Heisenberg GitHub Action

AI-powered root cause analysis for Playwright test failures.

## Features

- Analyzes Playwright JSON reports to identify failed tests
- Uses AI (Claude, OpenAI, or Gemini) to diagnose root causes
- Detects flaky test patterns
- Provides confidence-scored diagnoses
- Posts analysis as PR comments
- Supports container logs for additional context

## Usage

```yaml
- name: Run Playwright Tests
  run: npx playwright test --reporter=json --output=results.json
  continue-on-error: true

- name: Analyze Test Failures
  uses: kamilpajak/heisenberg/action@v1
  with:
    report-path: results.json
    api-key: ${{ secrets.ANTHROPIC_API_KEY }}
    provider: claude
```

## Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `report-path` | Yes | - | Path to Playwright JSON report file |
| `api-key` | Yes | - | API key for LLM provider |
| `provider` | No | `claude` | LLM provider (`claude`, `openai`, or `gemini`) |
| `model` | No | - | Specific model to use |
| `fail-on-flaky` | No | `false` | Fail workflow if flaky tests detected |
| `container-logs` | No | - | Path to container logs for context |
| `post-comment` | No | `false` | Post analysis as PR comment |
| `github-token` | No | - | GitHub token for PR comments |

## Outputs

| Output | Description |
|--------|-------------|
| `analysis` | Full JSON analysis result |
| `failed-tests-count` | Number of failed tests |
| `flaky-detected` | Whether flaky tests were detected |

## Examples

### Basic Usage

```yaml
name: Test Analysis

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run Tests
        run: npx playwright test --reporter=json --output=test-results.json
        continue-on-error: true

      - name: Analyze Failures
        uses: kamilpajak/heisenberg/action@v1
        with:
          report-path: test-results.json
          api-key: ${{ secrets.ANTHROPIC_API_KEY }}
```

### With OpenAI

```yaml
- name: Analyze Failures
  uses: kamilpajak/heisenberg/action@v1
  with:
    report-path: test-results.json
    api-key: ${{ secrets.OPENAI_API_KEY }}
    provider: openai
    model: gpt-4o
```

### With Gemini

```yaml
- name: Analyze Failures
  uses: kamilpajak/heisenberg/action@v1
  with:
    report-path: test-results.json
    api-key: ${{ secrets.GOOGLE_API_KEY }}
    provider: gemini
    model: gemini-3-pro-preview
```

### Post PR Comment

```yaml
- name: Analyze Failures
  uses: kamilpajak/heisenberg/action@v1
  with:
    report-path: test-results.json
    api-key: ${{ secrets.ANTHROPIC_API_KEY }}
    post-comment: true
    github-token: ${{ secrets.GITHUB_TOKEN }}
```

### Fail on Flaky Tests

```yaml
- name: Analyze Failures
  uses: kamilpajak/heisenberg/action@v1
  with:
    report-path: test-results.json
    api-key: ${{ secrets.ANTHROPIC_API_KEY }}
    fail-on-flaky: true
```

### With Container Logs

```yaml
- name: Save Docker Logs
  if: failure()
  run: docker-compose logs > docker-logs.txt

- name: Analyze Failures
  uses: kamilpajak/heisenberg/action@v1
  with:
    report-path: test-results.json
    api-key: ${{ secrets.ANTHROPIC_API_KEY }}
    container-logs: docker-logs.txt
```

### Using Outputs

```yaml
- name: Analyze Failures
  id: heisenberg
  uses: kamilpajak/heisenberg/action@v1
  with:
    report-path: test-results.json
    api-key: ${{ secrets.ANTHROPIC_API_KEY }}

- name: Check Results
  run: |
    echo "Failed tests: ${{ steps.heisenberg.outputs.failed-tests-count }}"
    echo "Flaky detected: ${{ steps.heisenberg.outputs.flaky-detected }}"
```

## Complete Workflow Example

```yaml
name: E2E Tests with AI Analysis

on:
  pull_request:
    branches: [main]

permissions:
  pull-requests: write
  contents: read

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: 20

      - name: Install Dependencies
        run: npm ci

      - name: Run Playwright Tests
        run: npx playwright test --reporter=json --output=test-results.json
        continue-on-error: true

      - name: Analyze with Heisenberg
        if: always()
        uses: kamilpajak/heisenberg/action@v1
        with:
          report-path: test-results.json
          api-key: ${{ secrets.ANTHROPIC_API_KEY }}
          provider: claude
          post-comment: true
          github-token: ${{ secrets.GITHUB_TOKEN }}
          fail-on-flaky: true
```

## License

MIT
