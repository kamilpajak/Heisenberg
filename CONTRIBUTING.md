# Contributing to Heisenberg

Thank you for your interest in contributing to Heisenberg! This document provides guidelines and instructions for contributing.

## Code of Conduct

Please be respectful and constructive in all interactions. We're all here to make testing better.

## Development Setup

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- Docker (for running integration tests)

### Getting Started

1. **Fork and clone the repository**

```bash
git clone https://github.com/YOUR_USERNAME/heisenberg.git
cd heisenberg
```

2. **Create a virtual environment**

```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. **Install dependencies**

```bash
uv pip install -e ".[dev]"
```

4. **Verify the setup**

```bash
pytest
```

## Code Style

We use automated tools to maintain consistent code style:

### Linting with Ruff

```bash
# Check for issues
ruff check src tests

# Auto-fix issues
ruff check --fix src tests
```

### Type Checking

```bash
# Run mypy (optional but recommended)
mypy src
```

### Pre-commit Hooks

We recommend setting up pre-commit hooks:

```bash
pre-commit install
```

This will run linting and formatting checks before each commit.

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=heisenberg --cov-report=term-missing

# Run specific test file
pytest tests/test_playwright_parser.py

# Run with verbose output
pytest -v
```

### Test Structure

We follow the **Given-When-Then** (or Arrange-Act-Assert) pattern:

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

### Writing New Tests

1. Place tests in the `tests/` directory
2. Name test files `test_*.py`
3. Use descriptive test names that explain the expected behavior
4. One assertion concept per test
5. Use fixtures for common setup

## Pull Request Guidelines

### Before Submitting

1. **Create a branch** with a descriptive name:
   - `feature/add-jest-support`
   - `bugfix/fix-timestamp-parsing`
   - `docs/update-readme`

2. **Write tests** for any new functionality

3. **Run the test suite** and ensure all tests pass:
   ```bash
   pytest
   ```

4. **Run the linter** and fix any issues:
   ```bash
   ruff check src tests
   ```

5. **Update documentation** if you're adding or changing features

### PR Process

1. **Open a Pull Request** against the `main` branch

2. **Fill out the PR template** with:
   - A clear description of the changes
   - The motivation/context
   - How to test the changes
   - Any breaking changes

3. **Wait for review** - maintainers will review your PR and may request changes

4. **Address feedback** - make any requested changes and push updates

5. **Merge** - once approved, a maintainer will merge your PR

### Commit Messages

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): description

[optional body]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `test`: Adding or updating tests
- `build`: Build system changes
- `ci`: CI configuration changes
- `chore`: Other changes

Examples:
```
feat(parser): add support for Playwright HTML reports
fix(docker): handle container not found error gracefully
docs(readme): add troubleshooting section
test(compressor): add edge case tests for empty logs
```

## Architecture Overview

```
src/heisenberg/
├── __init__.py          # Package exports
├── cli.py               # Command-line interface
├── playwright_parser.py # Playwright report parsing
├── docker_logs.py       # Docker log collection
├── log_compressor.py    # Log filtering and compression
├── prompt_builder.py    # LLM prompt construction
├── llm_client.py        # Anthropic API client
├── diagnosis.py         # Response parsing
├── ai_analyzer.py       # AI analysis orchestration
└── github_comment.py    # PR comment formatting
```

## Reporting Issues

### Bug Reports

When reporting bugs, please include:

1. **Environment** - Python version, OS, package version
2. **Steps to reproduce** - Minimal example to trigger the bug
3. **Expected behavior** - What should happen
4. **Actual behavior** - What actually happens
5. **Error messages** - Full stack traces if applicable

### Feature Requests

When requesting features:

1. **Use case** - Why do you need this feature?
2. **Proposed solution** - How do you envision it working?
3. **Alternatives** - Have you considered other approaches?

## Questions?

- Open a [GitHub Discussion](https://github.com/kamilpajak/heisenberg/discussions) for questions
- Check existing issues before creating new ones
- Join our community chat (coming soon)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
