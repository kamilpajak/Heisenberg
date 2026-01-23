"""Database connection and session management for Heisenberg backend."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.ext.asyncio import (
    create_async_engine as _create_async_engine,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

from heisenberg.backend.config import Settings


def create_async_engine(database_url: str, echo: bool = False) -> AsyncEngine:
    """
    Create an async SQLAlchemy engine.

    Args:
        database_url: PostgreSQL connection URL.
        echo: Whether to log SQL statements.

    Returns:
        AsyncEngine instance.
    """
    # Convert postgresql:// to postgresql+asyncpg://
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    return _create_async_engine(
        database_url,
        echo=echo,
        pool_pre_ping=True,
    )


def get_session_maker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """
    Create an async session maker.

    Args:
        engine: SQLAlchemy async engine.

    Returns:
        Async session maker.
    """
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


# Global instances (initialized at app startup)
_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


def init_db(settings: Settings) -> None:
    """
    Initialize database engine and session maker.

    Args:
        settings: Application settings.
    """
    global _engine, _session_maker
    _engine = create_async_engine(settings.database_url, echo=settings.debug)
    _session_maker = get_session_maker(_engine)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that yields database sessions.

    Yields:
        AsyncSession for database operations.
    """
    if _session_maker is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")

    async with _session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_db() -> None:
    """Close database connections."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
