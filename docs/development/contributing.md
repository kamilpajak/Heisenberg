# Contributing

## Development Setup

1. Clone the repository:

```bash
git clone https://github.com/kamilpajak/Heisenberg.git
cd Heisenberg
```

2. Install dependencies:

```bash
uv sync --all-extras --all-groups
```

3. Install pre-commit hooks:

```bash
pre-commit install
```

## Running Tests

```bash
uv run pytest
```

## Code Quality

The project uses several tools:

- **ruff**: Linting and formatting
- **ty**: Type checking
- **tach**: Architecture enforcement

Run all checks:

```bash
uv run ruff check src/ tests/
uv run ty check
uv run tach check
```
