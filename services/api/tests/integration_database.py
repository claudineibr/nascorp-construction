import os

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings


def get_integration_database_url() -> str:
    return os.environ.get("CONSTRUCTION_DATABASE_URL", settings.database_url)


async def create_reachable_engine_or_skip():
    engine = create_async_engine(get_integration_database_url())
    try:
        async with engine.connect() as connection:
            await connection.execute(text("select 1"))
    except (OSError, SQLAlchemyError) as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL integration database is unavailable: {exc}")

    return engine
