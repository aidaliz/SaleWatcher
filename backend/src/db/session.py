"""Database session configuration."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config.settings import get_settings

# Create engine at module level
_engine = None
_session_factory = None


def get_async_engine():
    """Create async database engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        # Convert postgresql:// to postgresql+asyncpg://
        database_url = settings.database_url.replace(
            "postgresql://", "postgresql+asyncpg://"
        )
        _engine = create_async_engine(
            database_url,
            echo=settings.debug,
            pool_pre_ping=True,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get async session factory (singleton)."""
    global _session_factory
    if _session_factory is None:
        engine = get_async_engine()
        _session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory

