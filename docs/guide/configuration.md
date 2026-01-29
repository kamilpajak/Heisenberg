# Configuration

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `ANTHROPIC_API_KEY` | Anthropic API key for AI analysis | Yes |
| `GITHUB_TOKEN` | GitHub token for fetching artifacts | For GitHub integration |
| `OPENAI_API_KEY` | OpenAI API key (alternative provider) | No |
| `GOOGLE_API_KEY` | Google AI API key (alternative provider) | No |

## LLM Providers

Heisenberg supports multiple LLM providers:

- **Anthropic Claude** (default)
- **OpenAI GPT**
- **Google Gemini**

Set the provider via environment variable:

```bash
export LLM_PROVIDER="anthropic"  # or "openai", "google"
```
