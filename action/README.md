# Heisenberg GitHub Action

AI-powered root cause analysis for Playwright test failures.

## Features

- Analyzes Playwright JSON reports to identify failed tests
- Uses AI (Claude or OpenAI) to diagnose root causes
- Detects flaky test patterns
- Provides confidence-scored diagnoses
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
| `provider` | No | `claude` | LLM provider (`claude` or `openai`) |
| `fail-on-flaky` | No | `false` | Fail workflow if flaky tests detected |
| `model` | No | - | Specific model to use |
| `container-logs` | No | - | Path to container logs for context |

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

- name: Comment on PR
  if: github.event_name == 'pull_request'
  uses: actions/github-script@v7
  with:
    script: |
      const analysis = `${{ steps.heisenberg.outputs.analysis }}`;
      const failedCount = '${{ steps.heisenberg.outputs.failed-tests-count }}';

      github.rest.issues.createComment({
        issue_number: context.issue.number,
        owner: context.repo.owner,
        repo: context.repo.repo,
        body: `## Test Analysis\n\n**Failed Tests:** ${failedCount}\n\n\`\`\`json\n${analysis}\n\`\`\``
      });
```

## License

MIT
