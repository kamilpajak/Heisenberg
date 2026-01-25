# Roadmap

This document outlines the planned development direction for Heisenberg.

## Completed

### Core Features
- Playwright JSON report parsing with full test result extraction
- AI-powered root cause analysis (Claude, OpenAI, Gemini)
- Docker container log collection with time-window correlation
- GitHub PR comment integration
- Confidence scoring for diagnoses
- CLI tool (`heisenberg analyze`, `heisenberg fetch-github`)
- GitHub Action for CI/CD integration

### Backend API
- FastAPI REST API
- PostgreSQL database with async support
- Rate limiting (sliding window)
- Structured JSON logging with request tracing
- Usage tracking and feedback collection
- Multi-LLM provider architecture with automatic fallback

## In Progress

### Web Dashboard
- Historical analysis viewer
- Usage statistics and cost tracking
- Organization management

## Planned

### Additional CI/CD Platforms
- GitLab CI integration
- Jenkins integration
- CircleCI integration

### Additional Test Frameworks
- Cypress support
- Selenium support
- Jest support

### Enhanced Analysis
- Pattern recognition across multiple failures (pgvector)
- Kubernetes log collection
- Infrastructure metrics correlation (CPU, memory, GC)

### Integrations
- Slack notifications
- Discord notifications
- Webhook support for custom integrations

## Contributing

We welcome contributions! If you're interested in working on any of these features, please:

1. Check [GitHub Issues](https://github.com/kamilpajak/heisenberg/issues) for existing discussions
2. Open a new issue to discuss your approach before starting work
3. See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines

## Feedback

Have a feature request? [Open an issue](https://github.com/kamilpajak/heisenberg/issues/new) and let us know what would make Heisenberg more useful for your team.
