# -*- coding: utf-8 -*-
"""Semeia uma medicao de demonstracao com as CINCO situacoes da linha da FVS.

Existe so para a conferencia visual. `python seed_demo_fvs.py --limpar` remove.
"""
import asyncio
import sys
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

sys.path.insert(0, ".")
from app.core.config import settings  # noqa: E402

COMPANY = uuid.UUID("00000000-0000-0000-0000-000000000001")
USER = uuid.UUID("00000000-0000-0000-0000-000000000001")
PERSON = uuid.UUID("00000000-0000-0000-0000-000000000001")
PROJECT_CODE = "OBRA-DEMO-FVS"

# (descricao, metodo, [(status, comentario, dias_atras)])
LINES = [
    ("TERRENO LIMPO, SEM VEGETACAO", "INSPECAO VISUAL", [("compliant", None, 3)]),
    (
        "COMPACTACAO DAS CAMADAS",
        "REGUA DE 2 M EM 3 PONTOS",
        [("non_compliant", "camada 3 solta no canto sul", 2)],
    ),
    (
        "HOMOGENEIDADE DAS CAMADAS",
        "INSPECAO VISUAL",
        [
            ("non_compliant", "material heterogeneo na faixa central", 5),
            ("non_compliant", "refeito parcialmente, ainda irregular", 3),
            ("compliant", None, 1),
        ],
    ),
    ("COTA DE PROJETO", "TRENA A LASER", []),
    (
        "DRENAGEM PROVISORIA",
        "INSPECAO VISUAL",
        [
            ("non_compliant", "sem canaleta no trecho norte", 6),
            ("waived", "trecho removido do contrato pelo aditivo 4", 1),
        ],
    ),
]


async def run(statements):
    engine = create_async_engine(settings.database_url, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        for sql, params in statements:
            await conn.execute(text(sql), params)
    await engine.dispose()


async def fetch_one(sql, params):
    engine = create_async_engine(settings.database_url)
    async with engine.connect() as conn:
        row = (await conn.execute(text(sql), params)).first()
    await engine.dispose()
    return row


async def clear():
    await run(
        [
            (
                "DELETE FROM construction.construction_measurements m"
                " USING construction.construction_projects p"
                " WHERE m.project_id = p.id AND p.code = :code",
                {"code": PROJECT_CODE},
            ),
            ("DELETE FROM construction.construction_projects WHERE code = :code", {"code": PROJECT_CODE}),
        ]
    )
    print("cenario de demonstracao removido.")


async def seed():
    await clear()
    project, measurement, item = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    unit, phase = uuid.uuid4(), uuid.uuid4()
    statements = [
        (
            "INSERT INTO construction.construction_projects (id, company_id, code, name, status)"
            " VALUES (:id, :company, :code, 'RESIDENCIAL DEMONSTRACAO FVS', 'active')",
            {"id": project, "company": COMPANY, "code": PROJECT_CODE},
        ),
        # A tela de medicoes vive DENTRO da unidade, nao da obra: sem unidade e
        # fase, o cenario nao aparece em lugar nenhum.
        (
            "INSERT INTO construction.construction_units"
            " (id, company_id, project_id, code, unit_type, sale_price, status)"
            " VALUES (:id, :company, :project, 'APTO-101', 'apartment', 320000, 'available')",
            {"id": unit, "company": COMPANY, "project": project},
        ),
        (
            "INSERT INTO construction.construction_schedule_phases"
            " (id, company_id, project_id, sequence_order, name, status, progress_percent)"
            " VALUES (:id, :company, :project, 1, 'FUNDACAO E ATERRO', 'in_progress', 40)",
            {"id": phase, "company": COMPANY, "project": project},
        ),
        (
            "INSERT INTO construction.construction_measurements"
            " (id, company_id, project_id, unit_id, schedule_phase_id, code, sequence_number,"
            "  measured_amount, due_date, status)"
            " VALUES (:id, :company, :project, :unit, :phase, 'MED-DEMO-01', 1, 48500, :due, 'draft')",
            {
                "id": measurement,
                "company": COMPANY,
                "project": project,
                "unit": unit,
                "phase": phase,
                "due": date(2026, 10, 30),
            },
        ),
        (
            "INSERT INTO construction.construction_measurement_items"
            " (id, company_id, measurement_id, sequence_number, description, amount,"
            "  start_date, inspector_person_id, inspection_status, created_by_user_id)"
            " VALUES (:id, :company, :measurement, 1, 'ATERRO / COMPACTACAO DE ATERRO', 48500,"
            "         :start, :person, 'non_compliant', :user)",
            {
                "id": item,
                "company": COMPANY,
                "measurement": measurement,
                "start": date(2026, 9, 10),
                "person": PERSON,
                "user": USER,
            },
        ),
    ]

    now = datetime.now(tz=UTC)
    for position, (description, method, rounds) in enumerate(LINES, start=1):
        line = uuid.uuid4()
        last = rounds[-1] if rounds else None
        statements.append(
            (
                "INSERT INTO construction.construction_measurement_item_inspections"
                " (id, company_id, measurement_item_id, sequence_number, description,"
                "  verification_method, section_name, inspector_person_id, status, rounds_count,"
                "  last_verified_at)"
                " VALUES (:id, :company, :item, :seq, :description, :method, 'GERAL', :person,"
                "         :status, :count, :last_at)",
                {
                    "id": line,
                    "company": COMPANY,
                    "item": item,
                    "seq": position,
                    "description": description,
                    "method": method,
                    "person": PERSON,
                    "status": last[0] if last else "pending",
                    "count": len(rounds),
                    "last_at": now if last else None,
                },
            )
        )
        for round_number, (status, comment, days_ago) in enumerate(rounds, start=1):
            statements.append(
                (
                    "INSERT INTO construction.construction_inspection_rounds"
                    " (id, company_id, inspection_id, measurement_item_id, sequence_number, status,"
                    "  verified_at, inspected_on, inspector_person_id, inspector_name,"
                    "  recorded_by_user_id, recorded_by_name, comment, source)"
                    " VALUES (:id, :company, :line, :item, :seq, :status, now() - make_interval(days => :days),"
                    "         (now() - make_interval(days => :days))::date, :person, 'CLAUDINEI NASCIMENTO',"
                    "         :user, 'CLAUDINEI NASCIMENTO', :comment, 'manual')",
                    {
                        "id": uuid.uuid4(),
                        "company": COMPANY,
                        "line": line,
                        "item": item,
                        "seq": round_number,
                        "status": status,
                        "days": days_ago,
                        "person": PERSON,
                        "user": USER,
                        "comment": comment,
                    },
                )
            )

    await run(statements)
    print("cenario semeado.")
    print("  obra:", PROJECT_CODE, "| unidade: APTO-101 | medicao: MED-DEMO-01")
    for description, _, rounds in LINES:
        state = rounds[-1][0] if rounds else "pending"
        print(f"  - {description:<32} {state:<14} {len(rounds)} rodada(s)")


asyncio.run(clear() if "--limpar" in sys.argv else seed())
