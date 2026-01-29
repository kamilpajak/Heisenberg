# Architecture

## Project Structure

```
src/heisenberg/
├── analysis/       # AI analysis components
├── backend/        # FastAPI REST API
├── cli/            # Command-line interface
├── core/           # Core models and types
├── integrations/   # External integrations (GitHub, Docker)
├── llm/            # LLM provider abstraction
├── parsers/        # Test report parsers
├── playground/     # Discovery and validation tools
└── utils/          # Shared utilities
```

## Key Components

### Parsers

Parse test reports from various formats:

- `PlaywrightParser`: Playwright JSON/HTML reports
- `JUnitParser`: JUnit XML reports

### LLM Router

Abstracts LLM provider selection and routing:

- Supports Anthropic, OpenAI, and Google
- Automatic fallback between providers
- Rate limiting and retry logic

### Analysis Pipeline

1. Parse test report
2. Extract failure context
3. Collect supplementary data (logs, screenshots)
4. Send to LLM for analysis
5. Format and return results
