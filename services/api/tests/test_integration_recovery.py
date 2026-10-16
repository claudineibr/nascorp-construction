from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.domain.events.constants import ConstructionEventType, ErpEventType
from app.domain.events.contracts import EventEnvelope
from app.domain.services.construction_integration_dispatcher import ConstructionIntegrationDispatcher
from app.domain.services.construction_project_service import ConstructionProjectService
from app.infrastructure.database.models import ConstructionProject, OutboxEvent, DeadLetterEvent
from app.infrastructure.events.integration_jobs import relay_integration_once
from app.infrastructure.repository.event_repository import EventRepository
from tests.integration_database import create_reachable_engine_or_skip


class Transport:
    def __init__(self):
        self.requests = []
        self.responses = {}

    async def deliver_event(self, *, event):
        self.requests.append(event.event_id)
        if event.event_id not in self.responses:
            self.responses[event.event_id] = EventEnvelope(
                event_id=uuid4(), event_type=ErpEventType.COST_CENTER_CREATED, event_version=1,
                company_id=event.company_id, aggregate_id=event.aggregate_id, aggregate_type='construction_project',
                occurred_at=datetime.now(UTC), producer='erp-api', correlation_id=event.correlation_id,
                causation_id=event.event_id, payload={'construction_project_id': str(event.aggregate_id),
                    'synthetic_cost_center_id': str(uuid4()), 'analytic_cost_center_id': str(uuid4())})
        return self.responses[event.event_id]


def request_event(company_id, project_id, event_type=ConstructionEventType.PROJECT_CREATED):
    return EventEnvelope(event_id=uuid4(), event_type=event_type, event_version=1,
        company_id=company_id, aggregate_id=project_id, aggregate_type='construction_project',
        occurred_at=datetime(2000, 1, 1, tzinfo=UTC), producer='construction-api', correlation_id=uuid4(),
        causation_id=None, payload={})


async def cleanup(session, company_id):
    await session.rollback()
    for model in (OutboxEvent, DeadLetterEvent, ConstructionProject):
        await session.execute(delete(model).where(model.company_id == company_id))
    await session.commit()


async def test_retry_reuses_event_and_commits_snapshot_with_publication(monkeypatch):
    engine = await create_reachable_engine_or_skip()
    company_id, project_id = uuid4(), uuid4()
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        session.add(ConstructionProject(id=project_id, company_id=company_id, code='RELAY', name='Relay', status='active'))
        event = request_event(company_id, project_id)
        row = await EventRepository(session).add_outbox_event(event)
        await session.commit()
        transport = Transport()
        original = ConstructionProjectService.apply_integration_response
        async def failed_application(self, **kwargs):
            raise RuntimeError('Falha local depois da entrega remota')
        try:
            monkeypatch.setattr(ConstructionProjectService, 'apply_integration_response', failed_application)
            await relay_integration_once(session, transport)
            row = await session.scalar(select(OutboxEvent).where(OutboxEvent.event_id == event.event_id))
            assert row.status == 'failed'
            project = await session.get(ConstructionProject, project_id)
            assert project.synthetic_cost_center_id is None
            row.next_attempt_at = None
            await session.commit()
            monkeypatch.setattr(ConstructionProjectService, 'apply_integration_response', original)
            await relay_integration_once(session, transport)
            await session.refresh(row)
            await session.refresh(project)
            assert row.status == 'published'
            assert project.synthetic_cost_center_id is not None
            assert transport.requests == [event.event_id, event.event_id]
            assert len(transport.responses) == 1
        finally:
            await cleanup(session, company_id)
    await engine.dispose()


async def test_legacy_measurement_is_quarantined_without_financial_request():
    engine = await create_reachable_engine_or_skip()
    company_id = uuid4()
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        event = request_event(company_id, uuid4(), ConstructionEventType.MEASUREMENT_APPROVED)
        row = await EventRepository(session).add_outbox_event(event)
        await session.commit()
        transport = Transport()
        try:
            await relay_integration_once(session, transport)
            await session.refresh(row)
            assert row.status == 'dead_letter'
            assert transport.requests == []
        finally:
            await cleanup(session, company_id)
    await engine.dispose()


async def test_legacy_delivery_is_not_replayed_blindly():
    engine = await create_reachable_engine_or_skip()
    company_id = uuid4()
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        row = await EventRepository(session).add_outbox_event(request_event(company_id, uuid4()), delivery_mode='legacy')
        await session.commit()
        transport = Transport()
        try:
            await relay_integration_once(session, transport)
            await session.refresh(row)
            assert row.status == 'dead_letter'
            assert transport.requests == []
        finally:
            await cleanup(session, company_id)
    await engine.dispose()


async def test_deleted_aggregate_is_not_sent_to_erp():
    engine = await create_reachable_engine_or_skip()
    company_id, project_id = uuid4(), uuid4()
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        session.add(ConstructionProject(id=project_id, company_id=company_id, code='DELETED', name='Excluída',
            status='active', deleted_at=datetime.now(UTC)))
        await EventRepository(session).add_outbox_event(request_event(company_id, project_id))
        await session.commit()
        transport = Transport()
        try:
            await relay_integration_once(session, transport)
            assert transport.requests == []
            row = await session.scalar(select(OutboxEvent).where(OutboxEvent.company_id == company_id))
            assert row.status == 'failed'
        finally:
            await cleanup(session, company_id)
    await engine.dispose()


async def test_synchronous_delivery_does_not_remain_pending():
    engine = await create_reachable_engine_or_skip()
    company_id = uuid4()
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        event = request_event(company_id, uuid4())
        try:
            await ConstructionIntegrationDispatcher(event_repository=EventRepository(session),
                event_transport=Transport(), integration_mode='sync_http').dispatch(event=event)
            await session.commit()
            row = await session.scalar(select(OutboxEvent).where(OutboxEvent.event_id == event.event_id))
            assert row.status == 'published'
        finally:
            await cleanup(session, company_id)
    await engine.dispose()


@pytest.mark.parametrize('mode', ['async_in_memory', 'async_sqs'])
async def test_async_modes_apply_durable_confirmation(mode):
    engine = await create_reachable_engine_or_skip()
    company_id, project_id = uuid4(), uuid4()
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        session.add(ConstructionProject(id=project_id, company_id=company_id, code='ASYNC', name='Assíncrona', status='active'))
        event, transport = request_event(company_id, project_id), Transport()
        try:
            result = await ConstructionIntegrationDispatcher(event_repository=EventRepository(session),
                event_transport=transport, integration_mode=mode).dispatch(event=event)
            await session.commit()
            assert result.response_event is None
            assert transport.requests == []
            await relay_integration_once(session, transport)
            project = await session.get(ConstructionProject, project_id)
            assert project.synthetic_cost_center_id is not None
            assert transport.requests == [event.event_id]
        finally:
            await cleanup(session, company_id)
    await engine.dispose()


async def test_later_event_waits_for_earlier_failed_event():
    from datetime import timedelta

    engine = await create_reachable_engine_or_skip()
    company_id, project_id = uuid4(), uuid4()
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        events = EventRepository(session)
        first = await events.add_outbox_event(request_event(company_id, project_id))
        later_event = request_event(company_id, project_id)
        later_event = EventEnvelope(**{**later_event.__dict__, 'occurred_at': datetime(2001, 1, 1, tzinfo=UTC)})
        await events.add_outbox_event(later_event)
        first.status = 'failed'
        first.next_attempt_at = datetime.now(UTC) + timedelta(hours=1)
        await session.commit()
        try:
            assert await events.next_integration_event() is None
        finally:
            await cleanup(session, company_id)
    await engine.dispose()
