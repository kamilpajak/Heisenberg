# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.1.0]: https://github.com/kamilpajak/Heisenberg/releases/tag/v0.1.0
