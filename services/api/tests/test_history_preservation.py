from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.domain.exceptions import ConstructionDomainError
from app.domain.services import ConstructionProjectService
from app.infrastructure.database.models import ConstructionProject, ConstructionMeasurement
from app.infrastructure.database.models import (
    ConstructionUnit, ConstructionMeasurementItem, ConstructionMeasurementItemInspection,
    ConstructionInspectionRound, ConstructionMeasurementItemOccurrence,
)
from app.infrastructure.repository.construction_repository import ConstructionRepository
from tests.integration_database import create_reachable_engine_or_skip


async def test_project_delete_preserves_rows_and_hides_them():
    engine = await create_reachable_engine_or_skip()
    company_id, actor_id = uuid4(), uuid4()
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        project = ConstructionProject(id=uuid4(), company_id=company_id, code='HISTORY', name='Histórico', status='active')
        session.add(project)
        await session.commit()
        repository = ConstructionRepository(session)
        session.info['actor_user_id'] = actor_id
        try:
            await ConstructionProjectService(repository=repository).delete_project(company_id=company_id, project_id=project.id)
            assert await session.scalar(text('SELECT count(*) FROM construction.construction_projects WHERE id=:id'), {'id': project.id}) == 1
            assert await repository.get_project(company_id=company_id, project_id=project.id) is None
            audit = await session.scalar(text('SELECT count(*) FROM construction.construction_deletion_audits WHERE entity_id=:id AND actor_user_id=:actor'), {'id': project.id, 'actor': actor_id})
            assert audit == 1
        finally:
            await session.rollback()
            await session.execute(text('DELETE FROM construction.construction_projects WHERE company_id=:company'), {'company': company_id})
            await session.execute(text('DELETE FROM construction.construction_deletion_audits WHERE company_id=:company'), {'company': company_id})
            await session.commit()
    await engine.dispose()


async def test_cascade_keeps_inspection_rounds_and_other_tenants():
    engine = await create_reachable_engine_or_skip()
    company, other = uuid4(), uuid4()
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        project = ConstructionProject(id=uuid4(), company_id=company, code='CASCADE', name='Preservar', status='active')
        foreign = ConstructionProject(id=uuid4(), company_id=other, code='CASCADE', name='Outra empresa', status='active')
        unit = ConstructionUnit(id=uuid4(), company_id=company, project_id=project.id, code='U-1', unit_type='apartment', status='available')
        measurement = ConstructionMeasurement(id=uuid4(), company_id=company, project_id=project.id, unit_id=unit.id,
            code='MED-000007', sequence_number=7, measured_amount=1, due_date=date.today(), status='draft')
        item = ConstructionMeasurementItem(id=uuid4(), company_id=company, measurement_id=measurement.id,
            sequence_number=1, description='Serviço', amount=1)
        inspection = ConstructionMeasurementItemInspection(id=uuid4(), company_id=company,
            measurement_item_id=item.id, sequence_number=1, description='Inspeção', status='compliant', rounds_count=1)
        occurrence = ConstructionMeasurementItemOccurrence(id=uuid4(), company_id=company,
            measurement_item_id=item.id, sequence_number=1, problem='Ocorrência', status='open')
        round_row = ConstructionInspectionRound(id=uuid4(), company_id=company, measurement_item_id=item.id,
            inspection_id=inspection.id, sequence_number=1, status='compliant', verified_at=datetime.now(UTC))
        for entity in (project, foreign, unit, measurement, item, inspection, occurrence, round_row):
            session.add(entity)
            await session.flush()
        await session.commit()
        repository = ConstructionRepository(session)
        try:
            with pytest.raises(ConstructionDomainError):
                await ConstructionProjectService(repository=repository).delete_project(company_id=company, project_id=project.id)
            await repository.delete(project)
            await repository.commit()
            for entity in (project, unit, measurement, item, inspection, occurrence):
                assert await session.scalar(text(f'SELECT count(*) FROM construction.{entity.__tablename__} WHERE id=:id AND deleted_at IS NOT NULL'), {'id': entity.id}) == 1
            assert await session.scalar(text('SELECT count(*) FROM construction.construction_inspection_rounds WHERE id=:id'), {'id': round_row.id}) == 1
            assert await repository.get_project(company_id=other, project_id=foreign.id) is foreign
            assert await repository.get_unit(company_id=company, unit_id=unit.id) is None
            assert await repository.get_project_by_code(company_id=company, code=project.code) is project
            assert await repository.get_next_measurement_sequence(company_id=company, unit_id=unit.id) == 8
        finally:
            await session.rollback()
            await session.execute(text('DELETE FROM construction.construction_projects WHERE company_id IN (:company,:other)'), {'company': company, 'other': other})
            await session.execute(text('DELETE FROM construction.construction_deletion_audits WHERE company_id=:company'), {'company': company})
            await session.commit()
    await engine.dispose()


async def test_project_delete_cannot_bypass_approved_measurement():
    engine = await create_reachable_engine_or_skip()
    company_id = uuid4()
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        project = ConstructionProject(id=uuid4(), company_id=company_id, code='LOCKED', name='Histórico', status='active')
        measurement = ConstructionMeasurement(id=uuid4(), company_id=company_id, project_id=project.id,
            code='LOCKED-OS', description='Aprovada', measured_amount=1, due_date=date.today(), status='approved')
        session.add_all([project, measurement])
        await session.commit()
        try:
            with pytest.raises(ConstructionDomainError):
                await ConstructionProjectService(repository=ConstructionRepository(session)).delete_project(company_id=company_id, project_id=project.id)
        finally:
            await session.rollback()
            await session.execute(text('DELETE FROM construction.construction_projects WHERE company_id=:company'), {'company': company_id})
            await session.commit()
    await engine.dispose()
