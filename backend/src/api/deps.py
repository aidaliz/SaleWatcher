"""FastAPI dependency injection utilities."""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting an async database session."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
