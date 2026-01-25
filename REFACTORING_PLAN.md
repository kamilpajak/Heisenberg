# Heisenberg - Plan Refaktoryzacji

> Dokument wygenerowany na podstawie code review z dnia 2026-01-25

## Status implementacji

| Faza | Status | Data | Uwagi |
|------|--------|------|-------|
| **Faza 1** | ✅ Zakończona | 2026-01-25 | TDD, 717 testów passed |
| **Faza 2** | ✅ Zakończona | 2026-01-25 | TDD, 729 testów passed |
| **Faza 3** | ✅ Zakończona | 2026-01-25 | TDD, 785 testów passed |
| **Faza 4** | ⏳ Opcjonalna | - | - |

---

## Podsumowanie

Heisenberg to dobrze zarchitekturyzowana aplikacja Python/FastAPI. Poniższy plan adresuje zidentyfikowane obszary do poprawy, uporządkowane według priorytetu i wpływu na system.

---

## Priorytety

| Priorytet | Problem | Wysiłek | Wpływ | Status |
|-----------|---------|---------|-------|--------|
| 🔴 HIGH | Rate limiter nie skaluje się | Średni | Wysoki | ✅ Naprawione |
| 🟡 MEDIUM | Settings ładowane przy każdym requescie | Niski | Średni | ✅ Naprawione |
| 🟡 MEDIUM | Duplikacja klientów LLM | Średni | Średni | ✅ Naprawione |
| 🟢 LOW | Globalny stan bazy danych | Średni | Niski | ⏳ Faza 4 |
| 🟢 LOW | Zbyt szeroki `except Exception` | Niski | Niski | ✅ Naprawione |

---

## Faza 1: Quick Wins ✅

> **Zakończona 2026-01-25** | Implementacja TDD | 12 nowych testów | 717 testów passed

### 1.1 Cache ustawień aplikacji ✅

**Plik:** `src/heisenberg/backend/config.py`

**Problem:** `get_settings()` tworzy nową instancję `Settings()` przy każdym wywołaniu, powodując powtórzony odczyt pliku `.env`.

**Zaimplementowane rozwiązanie:**

```python
from functools import lru_cache

@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
```

**Testy:** `tests/test_phase1_refactoring.py::TestSettingsCaching` (4 testy)

**Uwaga dla testów:** Użyć `get_settings.cache_clear()` w fixture jeśli testy modyfikują zmienne środowiskowe.

---

### 1.2 Zawężenie obsługi wyjątków w LLM Router ✅

**Plik:** `src/heisenberg/backend/llm/router.py`

**Problem:** Łapanie `Exception` maskuje błędy programistyczne.

**Zaimplementowane rozwiązanie:**

```python
# Dodane importy
import httpx
from anthropic import APIError as AnthropicAPIError
from openai import APIError as OpenAIAPIError

# Tuple z wyjątkami do łapania (z opcjonalnym Google API)
LLM_RECOVERABLE_ERRORS: tuple[type[Exception], ...] = (
    AnthropicAPIError,
    OpenAIAPIError,
    httpx.RequestError,
    httpx.HTTPStatusError,
)

# W metodzie analyze():
except LLM_RECOVERABLE_ERRORS as e:  # zamiast except Exception
```

**Testy:** `tests/test_phase1_refactoring.py::TestLLMRouterExceptionHandling` (8 testów)

---

## Faza 2: Skalowalność ✅

> **Zakończona 2026-01-25** | Implementacja TDD | 12 nowych testów | 729 testów passed

### 2.1 Zabezpieczenie Rate Limitera przed race conditions ✅

**Plik:** `src/heisenberg/backend/rate_limit.py`

**Problem:** Brak atomowości przy równoczesnych requestach; nie działa z wieloma workerami.

**Rozwiązanie (etap 1 - locki):**

```python
"""Rate limiting functionality for Heisenberg backend."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict

from heisenberg.backend.logging import get_logger

logger = get_logger(__name__)


class SlidingWindowRateLimiter:
    """Sliding window rate limiter for API requests."""

    def __init__(self, requests_per_minute: int = 60):
        """
        Initialize rate limiter.

        Args:
            requests_per_minute: Maximum requests allowed per minute.
        """
        self.rpm = requests_per_minute
        self.requests: dict[str, list[float]] = defaultdict(list)
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def is_allowed(self, key: str) -> tuple[bool, dict[str, str]]:
        """
        Check if a request is allowed for the given key.

        Args:
            key: Unique identifier for rate limiting (e.g., API key, IP).

        Returns:
            Tuple of (allowed, rate_limit_headers).
        """
        async with self._locks[key]:
            now = time.time()
            window_start = now - 60  # 1-minute sliding window

            # Clean old requests outside the window
            self.requests[key] = [t for t in self.requests[key] if t > window_start]

            current_count = len(self.requests[key])
            allowed = current_count < self.rpm

            if allowed:
                self.requests[key].append(now)
                remaining = self.rpm - current_count - 1
            else:
                remaining = 0

        headers = {
            "X-RateLimit-Limit": str(self.rpm),
            "X-RateLimit-Remaining": str(max(0, remaining)),
            "X-RateLimit-Reset": str(int(window_start + 60)),
        }

        if not allowed:
            logger.warning(
                "rate_limit_exceeded",
                key=key,
                limit=self.rpm,
                current_count=current_count,
            )

        return allowed, headers
```

**Plik:** `src/heisenberg/backend/middleware.py`

Zaktualizować wywołanie:

```python
# PRZED:
allowed, headers = self.limiter.is_allowed(key)

# PO:
allowed, headers = await self.limiter.is_allowed(key)
```

**Rozwiązanie (etap 2 - Redis) - opcjonalne dla produkcji:**

Dla prawdziwej skalowalności horyzontalnej rozważyć migrację do Redis z biblioteką `redis-py` lub użycie `slowapi` z backendem Redis.

---

## Faza 3: Konsolidacja kodu ✅

> **Zakończona 2026-01-25** | Implementacja TDD | 17 nowych testów | 785 testów passed

### 3.1 Ujednolicenie klientów LLM ✅

**Problem:** Duplikacja między `src/heisenberg/llm_client.py` (sync, CLI) a `src/heisenberg/backend/llm/*` (async, backend).

**Rozwiązanie:**

#### Krok 1: Utworzyć wspólną strukturę odpowiedzi

**Nowy plik:** `src/heisenberg/llm/models.py`

```python
"""Shared LLM response models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar


# Pricing per million tokens (as of 2025)
PRICING: dict[str, dict[str, float]] = {
    "claude-3-5-sonnet-20241022": {"input": 3.0, "output": 15.0},
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "gpt-4o": {"input": 2.5, "output": 10.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.6},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.0},
}

DEFAULT_INPUT_COST = 3.0
DEFAULT_OUTPUT_COST = 15.0


@dataclass
class LLMAnalysis:
    """Unified response from LLM analysis."""

    content: str
    input_tokens: int
    output_tokens: int
    model: str
    provider: str

    @property
    def total_tokens(self) -> int:
        """Total tokens used."""
        return self.input_tokens + self.output_tokens

    @property
    def estimated_cost(self) -> float:
        """Estimate cost in USD based on token usage."""
        pricing = PRICING.get(self.model, {})
        input_cost_per_million = pricing.get("input", DEFAULT_INPUT_COST)
        output_cost_per_million = pricing.get("output", DEFAULT_OUTPUT_COST)

        input_cost = self.input_tokens * input_cost_per_million / 1_000_000
        output_cost = self.output_tokens * output_cost_per_million / 1_000_000
        return input_cost + output_cost
```

#### Krok 2: Zaktualizować backend providers

Zmienić `src/heisenberg/backend/llm/claude.py` (i inne providery) aby zwracały `LLMAnalysis`:

```python
from heisenberg.llm.models import LLMAnalysis

async def analyze(...) -> LLMAnalysis:
    # ... existing code ...
    return LLMAnalysis(
        content=response.content[0].text,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        model=model,
        provider=self.name,
    )
```

#### Krok 3: Zaktualizować CLI client

Zmienić `src/heisenberg/llm_client.py` aby używał `LLMAnalysis` zamiast `LLMResponse`.

---

## Faza 4: Architektura (opcjonalne)

### 4.1 Przenieść stan bazy danych do app.state

**Problem:** Globalne `_engine` i `_session_maker` komplikują testowanie.

**Plik:** `src/heisenberg/backend/database.py`

```python
"""Database connection and session management."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine as _create_async_engine,
)

if TYPE_CHECKING:
    from fastapi import Request
    from sqlalchemy.ext.asyncio import AsyncEngine

from heisenberg.backend.config import Settings


def create_async_engine(database_url: str, echo: bool = False) -> AsyncEngine:
    """Create an async SQLAlchemy engine."""
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    return _create_async_engine(
        database_url,
        echo=echo,
        pool_pre_ping=True,
    )


def get_session_maker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create an async session maker."""
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


def init_db(settings: Settings) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Initialize database and return engine and session maker."""
    engine = create_async_engine(settings.database_url, echo=settings.debug)
    session_maker = get_session_maker(engine)
    return engine, session_maker


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields database sessions from app state."""
    session_maker = getattr(request.app.state, "session_maker", None)
    if session_maker is None:
        raise RuntimeError("Database not initialized. Check DATABASE_URL.")

    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

**Plik:** `src/heisenberg/backend/app.py`

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    from heisenberg.backend.config import get_settings
    from heisenberg.backend.database import init_db

    settings = get_settings()

    configure_logging(
        log_level=settings.log_level,
        json_format=settings.log_json_format,
    )

    if os.environ.get("DATABASE_URL"):
        engine, session_maker = init_db(settings)
        app.state.engine = engine
        app.state.session_maker = session_maker
        logger.info("database_initialized", database_url=settings.database_url[:20] + "...")

    logger.info("app_started", version=__version__)

    yield

    # Shutdown
    if hasattr(app.state, "engine"):
        await app.state.engine.dispose()
    logger.info("app_shutdown")
```

---

## Checklist implementacji

### Faza 1 (Quick Wins) ✅
- [x] Dodać `@lru_cache` do `get_settings()` — `src/heisenberg/backend/config.py`
- [x] Zawęzić `except Exception` w `LLMRouter` — `src/heisenberg/backend/llm/router.py`
- [x] Zaktualizować testy — `tests/test_phase1_refactoring.py` (nowy), `tests/test_backend_multi_llm.py`

### Faza 2 (Skalowalność) ✅
- [x] Dodać `asyncio.Lock` do rate limitera — `src/heisenberg/backend/rate_limit.py`
- [x] Zmienić `is_allowed()` na `async` — `src/heisenberg/backend/rate_limit.py`
- [x] Zaktualizować middleware — `src/heisenberg/backend/middleware.py`
- [x] Przetestować pod obciążeniem — `tests/test_phase2_refactoring.py` (12 testów), `tests/test_backend_rate_limit.py` (zaktualizowane)

### Faza 3 (Konsolidacja) ✅
- [x] Utworzyć `src/heisenberg/llm/models.py` — z `LLMAnalysis` dataclass i `PRICING` dict
- [x] Zaktualizować backend providers — `claude.py`, `openai.py`, `router.py`, `base.py`
- [x] Zaktualizować CLI client — `llm_client.py` z aliasem `LLMResponse = LLMAnalysis`
- [x] Zaktualizować adapter — `adapter.py` uproszczony, używa bezpośrednio `LLMAnalysis`
- [x] Przetestować — `tests/test_phase3_refactoring.py` (17 testów), istniejące testy zaktualizowane

### Faza 4 (Architektura)
- [ ] Przenieść stan DB do `app.state`
- [ ] Zaktualizować dependency `get_db()`
- [ ] Zaktualizować testy integracyjne

---

## Uwagi końcowe

- Każda faza może być wdrożona niezależnie
- Faza 1 powinna być priorytetem ze względu na niski wysiłek i natychmiastowe korzyści
- Faza 4 jest opcjonalna - obecne rozwiązanie działa, ale utrudnia testowanie
- Przed wdrożeniem Fazy 2 rozważyć czy aplikacja faktycznie będzie działać na wielu workerach
