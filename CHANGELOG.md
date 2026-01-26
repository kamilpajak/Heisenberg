# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-01-25

### Added

#### Google Gemini Support
- Added Google Gemini as third LLM provider option
- Updated default Gemini model to `gemini-3-pro-preview`

#### Unified Model
- Framework-agnostic `UnifiedTestRun` model for multi-framework support
- JUnit XML parser for broader test framework compatibility
- `PlaywrightTransformer` for converting Playwright reports to unified format

#### GitHub Action
- Reusable GitHub Action for test analysis in CI/CD pipelines
- GitHub artifacts support for fetching Playwright reports directly from workflow runs

#### Quality & Security
- SonarCloud integration for continuous code quality analysis
- API fuzz testing with Schemathesis for robustness validation
- Git hooks setup script for linting and conventional commits enforcement

#### Validation
- Real-world validation test suite with weekly CI workflow
- Self-generating validation tests (Phase 1)

### Changed

#### CLI Modular Refactoring
- Decomposed monolithic `cli.py` into modular `cli/` package
- Separated concerns: `commands.py`, `formatters.py`, `github_fetch.py`, `parsers.py`
- Improved maintainability and testability

#### Backend Improvements
- Major backend refactoring (phases 1-4): LLM client consolidation, shared models, improved architecture
- Reduced cognitive complexity in CLI and service modules
- Rate limiter cleanup method to prevent memory leaks
- Immutable pricing configuration using MappingProxyType

#### Dependencies
- Upgraded Python runtime from 3.11 to 3.14
- Updated GitHub Actions: checkout v6, setup-python v6, setup-uv v7, codecov-action v5

### Fixed
- Critical production readiness issues
- Missing `test_file` column in database schema
- GitHub Action alignment with CLI interface
- SonarCloud code smells, bugs, and security hotspots
- Regex pattern using negative lookahead instead of reluctant quantifier
- Backend dependencies installation in CI
- Cognitive complexity in `diagnosis.py` (refactored `_extract_confidence`)
- Unnecessary `list()` wrapper in `rate_limit.py`

### Documentation
- Comprehensive API documentation
- Public roadmap
- Updated README with improved examples

## [0.1.0] - 2025-01-24

### Added

#### Core Features
- Playwright JSON report parser with full test result extraction
- AI-powered root cause analysis using Claude API
- Structured diagnosis output with confidence scoring
- Support for container logs context in analysis

#### Backend API
- FastAPI backend with PostgreSQL database
- Multi-tenant organization and API key management
- Rate limiting with sliding window algorithm
- Structured JSON logging with request tracing
- Retry logic with exponential backoff for LLM calls

#### Multi-LLM Support
- Pluggable LLM provider architecture (Claude, OpenAI)
- Automatic fallback when primary provider fails
- LLM router with provider abstraction

#### Cost & Usage Tracking
- Per-request token and cost tracking
- Budget alerts with configurable thresholds
- Usage summary endpoints by organization

#### Feedback System
- Analysis feedback collection (helpful/not helpful)
- Feedback statistics aggregation

#### Async Task Queue
- Background task processing infrastructure
- Webhook notifications on task completion
- Task status tracking

#### DevOps
- Docker and docker-compose configuration
- GitHub Actions CI/CD pipeline (test, lint, build)
- Dependabot for automated dependency updates
- Alembic database migrations

### Developer Experience
- 529 automated tests with pytest
- Comprehensive OpenAPI documentation
- Type hints throughout codebase
- Ruff for linting and formatting

[0.2.0]: https://github.com/kamilpajak/Heisenberg/releases/tag/v0.2.0
[0.1.0]: https://github.com/kamilpajak/Heisenberg/releases/tag/v0.1.0
