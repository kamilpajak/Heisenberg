# CLI Reference

## Commands

### `heisenberg analyze`

Analyze test failures from a report file.

```bash
heisenberg analyze <path> [options]
```

**Arguments:**

- `path`: Path to the test report file

**Options:**

- `--format`: Report format (`playwright`, `junit`)
- `--output`: Output format (`text`, `json`)

### `heisenberg freeze`

Freeze a GitHub Actions run by downloading its artifacts.

```bash
heisenberg freeze [options]
```

**Options:**

- `--repo`, `-r`: Repository in `owner/repo` format
- `--run-id`: Workflow run ID
- `--output-dir`, `-o`: Output directory for artifacts
- `--token`: GitHub token (or set `GITHUB_TOKEN`)
