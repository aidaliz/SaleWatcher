from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db_session


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for database sessions."""
    async for session in get_db_session():
        yield session
