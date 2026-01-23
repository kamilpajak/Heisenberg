# Phase 5: Production Readiness - Implementation Plan

## Overview

Przygotowanie backendu Heisenberg do produkcji poprzez dodanie: migracji Alembic, strukturalnego logowania, retry logic, rate limiting i rozszerzonego health check.

**Podejście**: TDD (Red-Green-Refactor)
**Szacowana liczba nowych testów**: ~50-60

---

## Implementation Order

```
1. Structured Logging     <- fundament dla reszty
2. Retry Logic            <- potrzebne dla LLM calls
3. Enhanced Health Check  <- wykorzystuje logging
4. Rate Limiting          <- middleware z logowaniem
5. Alembic Migrations     <- na końcu, wymaga działającego backendu
```

---

## 1. Structured Logging

### Tests First (`tests/test_backend_logging.py`)

```python
class TestLoggingConfig:
    def test_logger_module_exists()
    def test_get_logger_returns_configured_logger()
    def test_logger_outputs_json_format()
    def test_log_includes_timestamp()
    def test_log_includes_level()

class TestRequestLogging:
    def test_request_id_middleware_exists()
    def test_request_id_generated_for_each_request()
    def test_request_id_in_response_header()
    def test_request_id_propagated_to_logs()

class TestLogContext:
    def test_log_context_manager_exists()
    def test_context_preserved_in_async_calls()
```

### Implementation Files

| File | Action | Description |
|------|--------|-------------|
| `src/heisenberg/backend/logging.py` | CREATE | Logger setup, JSON formatter, context vars |
| `src/heisenberg/backend/middleware.py` | CREATE | RequestIDMiddleware |
| `src/heisenberg/backend/config.py` | MODIFY | Add `log_level`, `log_format` settings |
| `src/heisenberg/backend/app.py` | MODIFY | Add middleware, init logging in lifespan |

### Technical Approach

```python
# logging.py
import structlog
from contextvars import ContextVar

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")

def configure_logging(log_level: str = "INFO", json_format: bool = True):
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            add_request_id,  # custom processor
            structlog.processors.JSONRenderer() if json_format else ...
        ]
    )

def get_logger(name: str) -> structlog.BoundLogger:
    return structlog.get_logger(name)
```

---

## 2. Retry Logic

### Tests First (`tests/test_backend_retry.py`)

```python
class TestRetryDecorator:
    def test_retry_decorator_exists()
    def test_retry_succeeds_on_first_attempt()
    def test_retry_retries_on_failure()
    def test_retry_respects_max_retries()
    def test_retry_uses_exponential_backoff()
    def test_retry_adds_jitter()
    def test_retry_logs_attempts()

class TestRetryableErrors:
    def test_retries_on_timeout_error()
    def test_retries_on_rate_limit_error()
    def test_does_not_retry_on_auth_error()
    def test_does_not_retry_on_validation_error()

class TestRetryConfig:
    def test_settings_has_retry_config()
    def test_max_retries_default()
    def test_base_delay_default()
```

### Implementation Files

| File | Action | Description |
|------|--------|-------------|
| `src/heisenberg/backend/retry.py` | CREATE | Retry decorator with backoff |
| `src/heisenberg/backend/config.py` | MODIFY | Add retry settings |
| `src/heisenberg/backend/services/analyze.py` | MODIFY | Apply retry to LLM calls |

### Technical Approach

```python
# retry.py
import asyncio
import random
from functools import wraps

def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    retryable_exceptions: tuple = (TimeoutError, ConnectionError),
):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    if attempt == max_retries:
                        raise
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    delay *= (0.5 + random.random())  # jitter
                    logger.warning("retry_attempt", attempt=attempt, delay=delay)
                    await asyncio.sleep(delay)
        return wrapper
    return decorator
```

---

## 3. Enhanced Health Check

### Tests First (`tests/test_backend_health.py`)

```python
class TestHealthCheck:
    def test_health_endpoint_returns_200()
    def test_health_includes_version()
    def test_health_includes_status()

class TestHealthDatabase:
    def test_health_includes_database_status()
    def test_health_shows_db_connected_when_ok()
    def test_health_shows_db_error_when_failed()
    def test_health_includes_db_latency_ms()

class TestHealthDegraded:
    def test_health_returns_503_when_db_down()
    def test_health_returns_200_with_degraded_status()
```

### Implementation Files

| File | Action | Description |
|------|--------|-------------|
| `src/heisenberg/backend/health.py` | CREATE | Health check logic |
| `src/heisenberg/backend/schemas.py` | MODIFY | Add DetailedHealthResponse |
| `src/heisenberg/backend/app.py` | MODIFY | Update health endpoint |

### Technical Approach

```python
# health.py
async def check_database_health(session_maker) -> tuple[bool, float]:
    """Returns (is_healthy, latency_ms)"""
    start = time.perf_counter()
    try:
        async with session_maker() as session:
            await session.execute(text("SELECT 1"))
        latency = (time.perf_counter() - start) * 1000
        return True, latency
    except Exception:
        return False, 0.0

# schemas.py
class DetailedHealthResponse(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"]
    version: str
    database: DatabaseHealthStatus
    timestamp: datetime
```

---

## 4. Rate Limiting

### Tests First (`tests/test_backend_rate_limit.py`)

```python
class TestRateLimiter:
    def test_rate_limiter_exists()
    def test_allows_requests_under_limit()
    def test_blocks_requests_over_limit()
    def test_resets_after_window()
    def test_tracks_by_api_key()

class TestRateLimitMiddleware:
    def test_middleware_exists()
    def test_adds_rate_limit_headers()
    def test_returns_429_when_exceeded()
    def test_includes_retry_after_header()

class TestRateLimitConfig:
    def test_settings_has_rate_limit_config()
    def test_rate_limit_per_minute_default()
    def test_rate_limit_burst_default()
```

### Implementation Files

| File | Action | Description |
|------|--------|-------------|
| `src/heisenberg/backend/rate_limit.py` | CREATE | Sliding window rate limiter |
| `src/heisenberg/backend/middleware.py` | MODIFY | Add RateLimitMiddleware |
| `src/heisenberg/backend/config.py` | MODIFY | Add rate limit settings |
| `src/heisenberg/backend/app.py` | MODIFY | Register middleware |

### Technical Approach

```python
# rate_limit.py
from collections import defaultdict
import time

class SlidingWindowRateLimiter:
    def __init__(self, requests_per_minute: int = 60, burst: int = 10):
        self.rpm = requests_per_minute
        self.burst = burst
        self.requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str) -> tuple[bool, dict]:
        now = time.time()
        window_start = now - 60

        # Clean old requests
        self.requests[key] = [t for t in self.requests[key] if t > window_start]

        current_count = len(self.requests[key])
        allowed = current_count < self.rpm

        if allowed:
            self.requests[key].append(now)

        return allowed, {
            "X-RateLimit-Limit": str(self.rpm),
            "X-RateLimit-Remaining": str(max(0, self.rpm - current_count - 1)),
            "X-RateLimit-Reset": str(int(window_start + 60)),
        }
```

---

## 5. Alembic Migrations

### Tests First (`tests/test_backend_migrations.py`)

```python
class TestAlembicSetup:
    def test_alembic_ini_exists()
    def test_migrations_directory_exists()
    def test_env_py_exists()

class TestMigrationScripts:
    def test_initial_migration_exists()
    def test_migration_has_upgrade_function()
    def test_migration_has_downgrade_function()
    def test_migration_creates_organizations_table()
    def test_migration_creates_api_keys_table()
    def test_migration_creates_test_runs_table()
    def test_migration_creates_analyses_table()
```

### Implementation Files

| File | Action | Description |
|------|--------|-------------|
| `alembic.ini` | CREATE | Alembic config |
| `migrations/env.py` | CREATE | Async migration env |
| `migrations/script.py.mako` | CREATE | Migration template |
| `migrations/versions/001_initial.py` | CREATE | Initial schema |

### Technical Approach

```python
# migrations/env.py
from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine
from heisenberg.backend.models import Base

def run_migrations_online():
    connectable = create_async_engine(config.get_main_option("sqlalchemy.url"))

    async def do_run_migrations(connection):
        await connection.run_sync(do_run_migrations_sync)

    def do_run_migrations_sync(connection):
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()

    asyncio.run(do_run_migrations(connectable))
```

---

## Files Summary

### New Files (13)

| File | Purpose |
|------|---------|
| `tests/test_backend_logging.py` | Logging tests |
| `tests/test_backend_retry.py` | Retry logic tests |
| `tests/test_backend_health.py` | Health check tests |
| `tests/test_backend_rate_limit.py` | Rate limiting tests |
| `tests/test_backend_migrations.py` | Migration tests |
| `src/heisenberg/backend/logging.py` | Structured logging |
| `src/heisenberg/backend/retry.py` | Retry decorator |
| `src/heisenberg/backend/rate_limit.py` | Rate limiter |
| `src/heisenberg/backend/health.py` | Health check logic |
| `alembic.ini` | Alembic config |
| `migrations/env.py` | Migration environment |
| `migrations/script.py.mako` | Migration template |
| `migrations/versions/001_initial.py` | Initial schema |

### Modified Files (5)

| File | Changes |
|------|---------|
| `src/heisenberg/backend/config.py` | Add logging, retry, rate limit settings |
| `src/heisenberg/backend/middleware.py` | Add RequestID, RateLimit middleware |
| `src/heisenberg/backend/app.py` | Register middleware, init logging |
| `src/heisenberg/backend/schemas.py` | Add DetailedHealthResponse |
| `src/heisenberg/backend/services/analyze.py` | Apply retry decorator |

---

## Verification

### Po każdej części

```bash
# Run all tests
uv run pytest

# Check coverage
uv run pytest --cov=heisenberg --cov-report=term-missing

# Lint
uv run ruff check src tests
```

### Po całej fazie

```bash
# Start services
docker-compose up -d postgres

# Run migrations
uv run alembic upgrade head

# Test health endpoint
curl http://localhost:8000/health

# Test rate limiting
for i in {1..100}; do curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/health; done
```

---

## Dependencies

Dodać do `pyproject.toml`:

```toml
[project.optional-dependencies]
backend = [
    # existing...
    "structlog>=24.1.0",
]
```

---

## Timeline

| Component | Estimated Tests | Status |
|-----------|-----------------|--------|
| 1. Structured Logging | ~12 | Pending |
| 2. Retry Logic | ~12 | Pending |
| 3. Enhanced Health Check | ~10 | Pending |
| 4. Rate Limiting | ~12 | Pending |
| 5. Alembic Migrations | ~8 | Pending |
| **Total** | **~54** | |
