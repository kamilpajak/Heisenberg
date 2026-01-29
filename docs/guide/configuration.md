# Configuration

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GOOGLE_API_KEY` | Google AI API key for AI analysis | Yes |
| `GITHUB_TOKEN` | GitHub token for fetching artifacts | For GitHub integration |
| `ANTHROPIC_API_KEY` | Anthropic API key (alternative provider) | No |
| `OPENAI_API_KEY` | OpenAI API key (alternative provider) | No |

## LLM Providers

Heisenberg supports multiple LLM providers:

- **Google Gemini** (default)
- **Anthropic Claude**
- **OpenAI GPT**

Set the provider via environment variable:

```bash
export LLM_PROVIDER="google"  # or "anthropic", "openai"
```
