# API Overview

Heisenberg provides a REST API for integrating with other tools.

## Starting the Server

```bash
uvicorn heisenberg.backend.app:app --reload
```

## Endpoints

### `POST /analyze`

Submit a test report for analysis.

**Request:**

```json
{
  "report": "...",
  "format": "playwright"
}
```

**Response:**

```json
{
  "failures": [...],
  "analysis": {
    "root_cause": "...",
    "suggestion": "..."
  }
}
```

## Authentication

The API uses JWT tokens for authentication. See [Configuration](../guide/configuration.md) for setup details.
