"""FastAPI dependency injection utilities."""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import async_session_maker


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting an async database session."""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
