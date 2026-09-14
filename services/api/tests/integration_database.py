import os
from urllib.parse import urlsplit

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings


def _database_name(url: str) -> str:
    return urlsplit(url).path.lstrip("/")


def get_integration_database_url() -> str | None:
    """URL do banco de integracao, ou ``None`` quando nao ha um configurado.

    Nunca devolve o banco da aplicacao. Estes testes inserem e apagam linhas de
    verdade, e o fallback silencioso para ``settings.database_url`` fazia a
    suite rodar em cima do banco de desenvolvimento: bastava um DELETE de
    limpeza mal escopado para levar dado real junto.

    A guarda e o nome do banco, e nao a origem da variavel, porque o perigo nao
    e o .env.test faltar -- e ele faltar sem ninguem perceber. Sem um banco de
    teste configurado os testes de integracao pulam, o que aparece no relatorio.
    """
    url = os.environ.get("CONSTRUCTION_DATABASE_URL") or settings.database_url
    if not url:
        return None

    if "test" not in _database_name(url).lower():
        return None

    return url


async def create_reachable_engine_or_skip():
    url = get_integration_database_url()
    if url is None:
        pytest.skip(
            "Nenhum banco de teste configurado. Defina CONSTRUCTION_DATABASE_URL "
            "(ou tests/.env.test) apontando para um banco cujo nome contenha 'test' "
            "e aplique as migrations nele: "
            "CONSTRUCTION_DATABASE_URL=<url> alembic upgrade head"
        )

    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("select 1"))
    except (OSError, SQLAlchemyError) as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL integration database is unavailable: {exc}")

    return engine
