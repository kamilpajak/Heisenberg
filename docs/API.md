# Heisenberg API Documentation

REST API for the Heisenberg backend service.

## Base URL

```
http://localhost:8000
```

For production deployments, replace with your server URL.

## Authentication

The `/api/v1/analyze` endpoint requires an API key in the `X-API-Key` header:

```http
X-API-Key: YOUR_API_KEY
```

Requests without a valid API key receive `401 Unauthorized`.

> **Note:** Other endpoints (`/feedback`, `/tasks`, `/usage`) are currently unauthenticated. This may change in future versions.

---

## Health Endpoints

### `GET /health`

Simple health check.

**Response (200 OK)**
```json
{
  "status": "healthy",
  "version": "0.2.0"
}
```

### `GET /health/detailed`

Detailed health check with dependency status.

**Response (200 OK)**
```json
{
  "status": "healthy",
  "version": "0.2.0",
  "database": {
    "connected": true,
    "latency_ms": 15.5
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

| Status | Description |
|--------|-------------|
| `healthy` | All systems operational |
| `degraded` | Database latency > 1000ms |
| `unhealthy` | Database unreachable |

---

## Analysis

### `POST /api/v1/analyze`

Submit test failure data for AI-powered root cause analysis.

**Request Body**
```json
{
  "failed_tests": [
    {
      "test_name": "Login flow should redirect to dashboard",
      "error_message": "TimeoutError: locator.click: Timeout 30000ms exceeded",
      "stack_trace": "...",
      "started_at": "2024-01-15T10:23:17Z"
    }
  ],
  "logs": {
    "api": "2024-01-15T10:23:45 ERROR: connection pool exhausted",
    "database": "..."
  },
  "metadata": {
    "repository": "org/repo",
    "run_id": "123456789"
  }
}
```

**Response (200 OK)**
```json
{
  "analysis_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
  "diagnoses": [
    {
      "test_name": "Login flow should redirect to dashboard",
      "root_cause": "Database connection timeout in authentication service...",
      "evidence": ["Backend log: 'ERROR: connection pool exhausted'"],
      "suggested_fix": "Increase PostgreSQL connection pool size...",
      "confidence_score": 0.85
    }
  ]
}
```

> **Note:** This endpoint returns `501 Not Implemented` in the open-source version. Use the CLI or GitHub Action for analysis.

---

## Feedback

### `POST /api/v1/analyses/{analysis_id}/feedback`

Submit feedback on an analysis.

| Parameter | Type | Description |
|-----------|------|-------------|
| `analysis_id` | UUID | Analysis ID (path) |

**Request Body**
```json
{
  "is_helpful": true,
  "comment": "Spot on diagnosis!"
}
```

**Response (201 Created)**
```json
{
  "id": "f1e2d3c4-b5a6-7890-1234-567890abcdef",
  "analysis_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
  "is_helpful": true,
  "comment": "Spot on diagnosis!",
  "created_at": "2024-01-15T11:00:00Z"
}
```

### `GET /api/v1/feedback/stats`

Get aggregated feedback statistics.

**Response (200 OK)**
```json
{
  "total_feedback": 150,
  "helpful_count": 120,
  "not_helpful_count": 30,
  "helpful_percentage": 80.0
}
```

---

## Tasks

### `POST /api/v1/tasks`

Create an async background task.

**Request Body**
```json
{
  "organization_id": "org-uuid",
  "task_type": "historical_analysis",
  "payload": {
    "repository": "org/repo",
    "time_range_days": 90
  }
}
```

**Response (201 Created)**
```json
{
  "id": "t1a2s3k4-e5f6-7890-1234-567890abcdef",
  "task_type": "historical_analysis",
  "status": "pending",
  "payload": {...},
  "result": null,
  "error_message": null,
  "created_at": "2024-01-15T12:00:00Z",
  "started_at": null,
  "completed_at": null
}
```

### `GET /api/v1/tasks/{task_id}`

Get task status and result.

| Parameter | Type | Description |
|-----------|------|-------------|
| `task_id` | UUID | Task ID (path) |

**Response (200 OK)**
```json
{
  "id": "t1a2s3k4-e5f6-7890-1234-567890abcdef",
  "task_type": "historical_analysis",
  "status": "completed",
  "payload": {...},
  "result": {"common_failure_pattern": "database_deadlock"},
  "error_message": null,
  "created_at": "2024-01-15T12:00:00Z",
  "started_at": "2024-01-15T12:00:05Z",
  "completed_at": "2024-01-15T12:05:00Z"
}
```

| Status | Description |
|--------|-------------|
| `pending` | Task queued |
| `running` | Task in progress |
| `completed` | Task finished successfully |
| `failed` | Task failed (see `error_message`) |

---

## Usage

### `GET /api/v1/usage/summary`

Get usage summary for an organization.

| Parameter | Type | Description |
|-----------|------|-------------|
| `organization_id` | UUID | Organization ID (query, required) |
| `days` | int | Lookback period, 1-365 (query, default: 30) |

**Response (200 OK)**
```json
{
  "organization_id": "org-uuid",
  "period_start": "2023-12-15T00:00:00Z",
  "period_end": "2024-01-15T00:00:00Z",
  "total_requests": 1250,
  "total_input_tokens": 5000000,
  "total_output_tokens": 250000,
  "total_cost_usd": "123.45",
  "by_model": {
    "claude-3-5-sonnet-20241022": {"requests": 1000, "cost_usd": "100.00"},
    "gpt-4-turbo": {"requests": 250, "cost_usd": "23.45"}
  }
}
```

### `GET /api/v1/usage/by-model`

Get usage breakdown by LLM model.

| Parameter | Type | Description |
|-----------|------|-------------|
| `organization_id` | UUID | Organization ID (query, required) |
| `days` | int | Lookback period, 1-365 (query, default: 30) |

**Response (200 OK)**
```json
[
  {
    "model_name": "claude-3-5-sonnet-20241022",
    "requests": 1000,
    "input_tokens": 4000000,
    "output_tokens": 200000,
    "cost_usd": "100.00"
  },
  {
    "model_name": "gpt-4-turbo",
    "requests": 250,
    "input_tokens": 1000000,
    "output_tokens": 50000,
    "cost_usd": "23.45"
  }
]
```

---

## Error Responses

All endpoints return errors in this format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

| Code | Description |
|------|-------------|
| 400 | Bad Request - Invalid input |
| 401 | Unauthorized - Missing/invalid API key |
| 404 | Not Found - Resource doesn't exist |
| 429 | Too Many Requests - Rate limit exceeded |
| 500 | Internal Server Error |
| 501 | Not Implemented - Feature not available |
