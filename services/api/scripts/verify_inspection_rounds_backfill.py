# -*- coding: utf-8 -*-
"""Prova o backfill da 20260917_0025 com as QUATRO formas reais do MFCON.

Semeia no schema antigo (0024) uma linha de cada forma medida no legado em
2026-09-17 -- `A` sem reinspecao (43.141 registros), `A`+`AR` (36), so `R` (66) e
tudo em branco (1.002) --, sobe a migration, confere as rodadas e as derivadas,
desce, confere que as seis colunas antigas voltaram, sobe de novo e limpa.

NAO e um teste de pytest de proposito: ele derruba e sobe o schema, e rodar isso
dentro da suite arrastaria junto qualquer outro teste de integracao da mesma
sessao. Rode a mao antes de mergear uma mudanca na 0025:

    cd src/external/nascorp-construction/services/api
    python scripts/verify_inspection_rounds_backfill.py

Escreve SOMENTE no banco cujo nome termina em `/test`, e apaga o que criou.
"""
import asyncio
import os
import subprocess
import sys
import uuid
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.core.config import settings  # noqa: E402

TEST_URL = settings.database_url.rsplit("/", 1)[0] + "/test"
COMPANY = uuid.uuid4()
PROJECT, MEASUREMENT, ITEM = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
USER_A, USER_B = uuid.uuid4(), uuid.uuid4()

# (rotulo, first_status, second_status) -- as formas medidas no legado
SHAPES = [
    ("A_sem_AR", "compliant", "pending"),
    ("A_mais_AR", "compliant", "compliant"),
    ("so_R", "non_compliant", "pending"),
    ("tudo_NULL", "pending", "pending"),
]

failures = []


def check(label, got, expected):
    ok = got == expected
    print(f"  [{'ok    ' if ok else 'FALHOU'}] {label}: {got!r}")
    if not ok:
        failures.append(f"{label}: esperado {expected!r}, veio {got!r}")


def alembic(*args):
    env = dict(os.environ, CONSTRUCTION_DATABASE_URL=TEST_URL)
    done = subprocess.run(["alembic", *args], env=env, capture_output=True, text=True)
    if done.returncode != 0:
        print(done.stdout, done.stderr)
        raise SystemExit(f"alembic {' '.join(args)} falhou")


async def seed(conn):
    await conn.execute(
        text(
            "INSERT INTO construction.construction_projects (id, company_id, code, name, status)"
            " VALUES (:id, :company, :code, :name, 'active')"
        ),
        {"id": PROJECT, "company": COMPANY, "code": f"OBRA-{str(PROJECT)[:8]}", "name": "Obra da prova"},
    )
    await conn.execute(
        text(
            "INSERT INTO construction.construction_measurements"
            " (id, company_id, project_id, code, measured_amount, due_date, status)"
            " VALUES (:id, :company, :project, :code, 1000, CURRENT_DATE, 'draft')"
        ),
        {"id": MEASUREMENT, "company": COMPANY, "project": PROJECT, "code": f"MED-{str(MEASUREMENT)[:8]}"},
    )
    await conn.execute(
        text(
            "INSERT INTO construction.construction_measurement_items"
            " (id, company_id, measurement_id, sequence_number, description, amount, inspection_status)"
            " VALUES (:id, :company, :measurement, 1, 'Servico da prova', 1000, 'pending')"
        ),
        {"id": ITEM, "company": COMPANY, "measurement": MEASUREMENT},
    )
    for position, (label, first, second) in enumerate(SHAPES, start=1):
        await conn.execute(
            text(
                "INSERT INTO construction.construction_measurement_item_inspections"
                " (id, company_id, measurement_item_id, sequence_number, description,"
                "  first_status, first_status_at, first_status_by_user_id,"
                "  second_status, second_status_at, second_status_by_user_id)"
                " VALUES (:id, :company, :item, :seq, :description,"
                "         :first, :first_at, :first_user, :second, NULL, :second_user)"
            ),
            {
                "id": uuid.uuid4(),
                "company": COMPANY,
                "item": ITEM,
                "seq": position,
                "description": f"Linha {label}",
                "first": first,
                # A 2a verificacao do legado NUNCA teve data (bug do C#).
                "first_at": None,
                "first_user": None if first == "pending" else USER_A,
                "second": second,
                "second_user": None if second == "pending" else USER_B,
            },
        )
    # `now()` nao passa como bind; carimba a data da 1a onde ela existe.
    await conn.execute(
        text(
            "UPDATE construction.construction_measurement_item_inspections"
            "   SET first_status_at = now()"
            " WHERE company_id = :company AND first_status <> 'pending'"
        ),
        {"company": COMPANY},
    )


async def fetch(conn, sql, **params):
    return (await conn.execute(text(sql), {"company": COMPANY, "item": ITEM, **params})).all()


async def cleanup(conn):
    await conn.execute(
        text("DELETE FROM construction.construction_measurements WHERE company_id = :company"),
        {"company": COMPANY},
    )
    await conn.execute(
        text("DELETE FROM construction.construction_projects WHERE company_id = :company"),
        {"company": COMPANY},
    )


async def connect():
    return create_async_engine(TEST_URL, isolation_level="AUTOCOMMIT")


async def main():
    alembic("downgrade", "20260917_0024")
    engine = await connect()
    async with engine.connect() as conn:
        await cleanup(conn)
        await seed(conn)
    await engine.dispose()
    print("semeado no schema antigo (0024)\n")

    alembic("upgrade", "head")
    print("--- depois do upgrade ---")
    engine = await connect()
    async with engine.connect() as conn:
        rows = await fetch(
            conn,
            "SELECT i.description, r.sequence_number, r.status, r.source, r.verified_at IS NOT NULL"
            "  FROM construction.construction_measurement_item_inspections i"
            "  LEFT JOIN construction.construction_inspection_rounds r ON r.inspection_id = i.id"
            " WHERE i.company_id = :company ORDER BY i.sequence_number, r.sequence_number",
        )
        rounds = {}
        for description, seq, status, source, has_at in rows:
            rounds.setdefault(description, []).append(None if seq is None else (seq, status, source, has_at))

        check("A sem AR -> 1 rodada conforme", rounds["Linha A_sem_AR"], [(1, "compliant", "migration", True)])
        check(
            "A+AR -> 2 rodadas (a 2a herda a data da 1a)",
            rounds["Linha A_mais_AR"],
            [(1, "compliant", "migration", True), (2, "compliant", "migration", True)],
        )
        check("so R -> 1 rodada reprovada", rounds["Linha so_R"], [(1, "non_compliant", "migration", True)])
        check("tudo NULL -> nenhuma rodada", rounds["Linha tudo_NULL"], [None])

        derived = {
            d: (s, c, at)
            for d, s, c, at in await fetch(
                conn,
                "SELECT description, status, rounds_count, last_verified_at IS NOT NULL"
                "  FROM construction.construction_measurement_item_inspections"
                " WHERE company_id = :company ORDER BY sequence_number",
            )
        }
        check("derivada A sem AR", derived["Linha A_sem_AR"], ("compliant", 1, True))
        check("derivada A+AR", derived["Linha A_mais_AR"], ("compliant", 2, True))
        check("derivada so R", derived["Linha so_R"], ("non_compliant", 1, True))
        check("derivada tudo NULL", derived["Linha tudo_NULL"], ("pending", 0, False))

        status = (
            await fetch(
                conn,
                "SELECT inspection_status FROM construction.construction_measurement_items WHERE id = :item",
            )
        )[0][0]
        check("rollup do item (regra nova)", status, "non_compliant")
    await engine.dispose()

    alembic("downgrade", "20260917_0024")
    print("\n--- depois do downgrade ---")
    engine = await connect()
    async with engine.connect() as conn:
        legacy = {
            d: (f, fu, s, su)
            for d, f, fu, s, su in await fetch(
                conn,
                "SELECT description, first_status, first_status_by_user_id,"
                "       second_status, second_status_by_user_id"
                "  FROM construction.construction_measurement_item_inspections"
                " WHERE company_id = :company ORDER BY sequence_number",
            )
        }
        check("A sem AR volta", legacy["Linha A_sem_AR"], ("compliant", USER_A, "pending", None))
        check("A+AR volta com os dois usuarios", legacy["Linha A_mais_AR"], ("compliant", USER_A, "compliant", USER_B))
        check("so R volta", legacy["Linha so_R"], ("non_compliant", USER_A, "pending", None))
        check("tudo NULL volta", legacy["Linha tudo_NULL"], ("pending", None, "pending", None))
    await engine.dispose()

    alembic("upgrade", "head")
    print("\n--- depois do reupgrade ---")
    engine = await connect()
    async with engine.connect() as conn:
        again = {
            d: (s, c)
            for d, s, c, _ in await fetch(
                conn,
                "SELECT description, status, rounds_count, last_verified_at IS NOT NULL"
                "  FROM construction.construction_measurement_item_inspections"
                " WHERE company_id = :company ORDER BY sequence_number",
            )
        }
        check("reupgrade reconstroi as derivadas", again["Linha A_mais_AR"], ("compliant", 2))
        await cleanup(conn)
    await engine.dispose()
    print("\nlimpo.")

    if failures:
        print("\nFALHAS:")
        for failure in failures:
            print(" -", failure)
        raise SystemExit(1)
    print("\nTUDO CERTO")


asyncio.run(main())
