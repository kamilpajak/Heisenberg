# Contributing to Heisenberg

Thank you for your interest in contributing to Heisenberg! We welcome contributions of all kinds - bug reports, feature requests, documentation improvements, and code contributions.

## Code of Conduct

Please be respectful and constructive in all interactions. We're building a welcoming community where everyone can contribute and learn.

## Types of Contributions

- **Bug Reports** - Found something broken? [Open an issue](https://github.com/kamilpajak/heisenberg/issues/new?template=bug_report.yml)
- **Feature Requests** - Have an idea? [Start a discussion](https://github.com/kamilpajak/heisenberg/issues/new?template=feature_request.yml)
- **Documentation** - Help improve our docs
- **Code** - Fix bugs, add features, improve tests
- **Good First Issues** - Look for issues labeled [`good first issue`](https://github.com/kamilpajak/heisenberg/labels/good%20first%20issue)

## Development Setup

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- PostgreSQL 14+ (for backend development)
- Docker (for running integration tests)

### Quick Start (CLI only)

If you only want to work on the CLI tool:

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/heisenberg.git
cd heisenberg

# Create virtual environment
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install CLI dependencies
uv pip install -e ".[dev]"

# Run tests
pytest
```

### Full Setup (CLI + Backend API)

For backend development, you'll also need PostgreSQL:

```bash
# Install all dependencies (CLI + Backend)
uv pip install -e ".[dev,backend]"

# Copy environment template
cp .env.example .env
# Edit .env with your settings (especially DATABASE_URL)

# Start PostgreSQL (via Docker)
docker run -d \
  --name heisenberg-postgres \
  -e POSTGRES_USER=heisenberg \
  -e POSTGRES_PASSWORD=heisenberg \
  -e POSTGRES_DB=heisenberg \
  -p 5432:5432 \
  postgres:16

# Run database migrations
alembic upgrade head

# Start the API server
uvicorn heisenberg.backend.app:app --reload --port 8000
```

### Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | For AI | Claude API key |
| `OPENAI_API_KEY` | For AI | OpenAI API key |
| `GOOGLE_API_KEY` | For AI | Gemini API key |
| `DATABASE_URL` | For backend | PostgreSQL connection string |
| `SECRET_KEY` | For backend | JWT signing key |

At least one AI provider key is required for AI analysis features.

## Project Architecture

```
src/heisenberg/
├── __init__.py              # Package version
├── cli.py                   # Command-line interface
├── playwright_parser.py     # Playwright report parsing
├── docker_logs.py           # Docker log collection
├── log_compressor.py        # Log filtering and compression
├── llm_client.py            # LLM client (CLI)
├── ai_analyzer.py           # AI analysis orchestration
├── github_comment.py        # PR comment formatting
│
├── llm/                     # Shared LLM models
│   └── models.py            # LLMAnalysis dataclass, pricing
│
└── backend/                 # REST API (FastAPI)
    ├── app.py               # FastAPI application
    ├── config.py            # Settings management
    ├── database.py          # SQLAlchemy + PostgreSQL
    ├── models.py            # Database models
    ├── schemas.py           # Pydantic schemas
    ├── routers/             # API endpoints
    │   ├── analyze.py       # /api/v1/analyze
    │   ├── feedback.py      # /api/v1/feedback
    │   ├── usage.py         # /api/v1/usage
    │   └── tasks.py         # /api/v1/tasks
    └── llm/                  # LLM providers
        ├── base.py          # Abstract provider
        ├── claude.py        # Anthropic Claude
        ├── openai.py        # OpenAI GPT
        └── router.py        # Provider routing
```

## Testing

We use pytest and maintain **100% code coverage** with 848+ tests.

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=heisenberg --cov-report=term-missing

# Run specific test file
pytest tests/test_playwright_parser.py

# Run tests matching a pattern
pytest -k "test_parser"

# Skip slow fuzz tests
pytest -m "not fuzz"
```

### Test Structure

We follow the **Given-When-Then** (Arrange-Act-Assert) pattern:

```python
def test_parser_extracts_failed_tests(self, sample_report: dict):
    """Parser should extract all failed tests from the report."""
    # Given
    parser = PlaywrightParser()

    # When
    result = parser.parse(sample_report)

    # Then
    assert len(result.failed_tests) == 2
```

### Writing Tests

1. Place tests in `tests/` directory
2. Name test files `test_*.py`
3. Use descriptive names explaining expected behavior
4. One assertion concept per test
5. Mock external services (LLMs, APIs, Docker)
6. Maintain 100% coverage for new code

## Code Style

### Linting with Ruff

```bash
# Check for issues
ruff check src tests

# Auto-fix issues
ruff check --fix src tests

# Format code
ruff format src tests
```

### Pre-commit Hooks

We recommend setting up pre-commit hooks:

```bash
# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

## Commit Messages

We use [Conventional Commits](https://www.conventionalcommits.org/) for automated changelog generation:

```
type(scope): description

[optional body]
```

### Types

| Type | Description |
|------|-------------|
| `feat` | New feature (triggers minor version bump) |
| `fix` | Bug fix (triggers patch version bump) |
| `docs` | Documentation only |
| `style` | Code style (formatting, etc.) |
| `refactor` | Code refactoring |
| `perf` | Performance improvement |
| `test` | Adding/updating tests |
| `build` | Build system changes |
| `ci` | CI configuration |
| `chore` | Other changes |

### Examples

```bash
feat(parser): add support for Playwright HTML reports
fix(docker): handle container not found error gracefully
docs(readme): add troubleshooting section
test(compressor): add edge case tests for empty logs
refactor(llm): consolidate provider interfaces
```

## Pull Request Process

### Before Submitting

1. **Create a branch** with a descriptive name:
   ```bash
   git checkout -b feature/add-jest-support
   git checkout -b fix/timestamp-parsing
   ```

2. **Write tests** for any new functionality

3. **Run the test suite**:
   ```bash
   pytest
   ```

4. **Run the linter**:
   ```bash
   ruff check src tests
   ruff format --check src tests
   ```

5. **Update documentation** if needed

### Submitting

1. Push your branch and open a Pull Request against `main`
2. Fill out the PR description:
   - What changes were made
   - Why (link to issue if applicable)
   - How to test
   - Any breaking changes
3. Wait for CI checks to pass
4. Address review feedback
5. Maintainer will merge when approved

### CI/CD Pipeline

Every PR triggers GitHub Actions that run:
- **Test** - pytest with coverage
- **Lint** - ruff check and format
- **SonarCloud** - code quality analysis
- **Build** - Docker image build
- **Codecov** - coverage reporting

All checks must pass before merge.

## Adding a New LLM Provider

To add support for a new LLM (e.g., Mistral):

1. Create `src/heisenberg/backend/llm/mistral.py`:

```python
from heisenberg.backend.llm.base import LLMProvider
from heisenberg.llm.models import LLMAnalysis

class MistralProvider(LLMProvider):
    """Mistral AI provider."""

    async def analyze(self, prompt: str) -> LLMAnalysis:
        # Implementation here
        ...
```

2. Register in `src/heisenberg/backend/llm/router.py`

3. Add pricing to `src/heisenberg/llm/models.py`

4. Add tests in `tests/test_backend_llm_mistral.py`

5. Update documentation

## Reporting Issues

### Bug Reports

Include:
1. **Environment** - Python version, OS, Heisenberg version
2. **Steps to reproduce** - Minimal example
3. **Expected behavior** - What should happen
4. **Actual behavior** - What actually happens
5. **Error messages** - Full stack traces

### Feature Requests

Include:
1. **Use case** - Why do you need this?
2. **Proposed solution** - How should it work?
3. **Alternatives** - Other approaches considered

## Questions?

- Open a [GitHub Issue](https://github.com/kamilpajak/heisenberg/issues) for bugs/features
- Check [ROADMAP.md](ROADMAP.md) for planned features
- Review [docs/API.md](docs/API.md) for API documentation

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
