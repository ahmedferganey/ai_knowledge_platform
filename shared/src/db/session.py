"""
Async SQLAlchemy 2 engine and session factory.

Usage in FastAPI:
    async with AsyncSessionFactory() as session:
        ...

    # Or via dependency injection:
    async def endpoint(db: AsyncSession = Depends(get_db)):
        ...
"""

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from shared.src.config.settings import get_settings


@lru_cache(maxsize=1)
def _get_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        echo=settings.environment == "local",
    )


def get_engine() -> AsyncEngine:
    return _get_engine()


AsyncSessionFactory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=get_engine(),
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yields an AsyncSession and closes it on exit."""
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
