"""Database session configuration."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config.settings import get_settings


def get_async_engine():
    """Create async database engine."""
    settings = get_settings()
    # Convert postgresql:// to postgresql+asyncpg://
    database_url = settings.database_url.replace(
        "postgresql://", "postgresql+asyncpg://"
    )
    return create_async_engine(
        database_url,
        echo=settings.debug,
        pool_pre_ping=True,
    )


def async_session_maker() -> async_sessionmaker[AsyncSession]:
    """Create async session factory."""
    engine = get_async_engine()
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
