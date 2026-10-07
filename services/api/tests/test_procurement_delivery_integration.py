from decimal import Decimal
from datetime import UTC, datetime, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.domain.services.construction_project_service import ConstructionProjectService
from app.domain.events.contracts import EventEnvelope
from app.infrastructure.database.models import ConstructionProject, ConstructionProcurementRequest, ConstructionProcurementItem, OutboxEvent, DeadLetterEvent, ProcessedEvent
from app.infrastructure.repository.construction_repository import ConstructionRepository
from app.infrastructure.repository.event_repository import EventRepository
from app.infrastructure.events.outbox_relay import DatabaseOutboxRelay
from app.infrastructure.events.procurement_jobs import ProcurementPublisher
from tests.integration_database import create_reachable_engine_or_skip


@pytest.mark.asyncio
async def test_offline_erp_persists_submission_three_failures_and_manual_retry_keeps_event_id():
    engine = await create_reachable_engine_or_skip()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    company_id, project_id, request_id = uuid4(), uuid4(), uuid4()
    try:
        async with factory() as session:
            session.add(ConstructionProject(id=project_id, company_id=company_id, code=f"TEST-{project_id.hex[:8]}",
                name="Outbox test", status="active", project_type="residential_vertical"))
            session.add(ConstructionProcurementRequest(id=request_id, company_id=company_id, project_id=project_id,
                code="REQ-TEST", title="Material", estimated_amount=Decimal("10"), discount_amount=Decimal("0"),
                status="draft", submission_revision=0))
            await session.flush()
            session.add(ConstructionProcurementItem(id=uuid4(), company_id=company_id, procurement_request_id=request_id, sequence_number=1,
                product_id=uuid4(), product_code="TEST-1", product_description="Areia", quantity=Decimal("1"), unit_of_measure="UN",
                unit_price=Decimal("10"), line_total=Decimal("10")))
            await session.commit()
            offline = AsyncMock()
            offline.deliver_event.side_effect = RuntimeError("ERP offline")
            service = ConstructionProjectService(repository=ConstructionRepository(session), event_repository=EventRepository(session), erp_client=offline)
            submitted = await service.submit_procurement_request(company_id=company_id, procurement_request_id=request_id, actor_user_id=None)
            assert submitted.delivery_status == "sending"
            offline.deliver_event.assert_not_awaited()
            event = await EventRepository(session).latest_procurement_event(company_id=company_id, aggregate_id=request_id)
            event_id = event.event_id
            for _ in range(3):
                publisher = ProcurementPublisher(session)
                publisher.client = offline
                relay = DatabaseOutboxRelay(repository=EventRepository(session), publisher=publisher)
                await relay.relay_pending(event_type="construction.procurement.requested.v2")
            await session.refresh(submitted)
            assert submitted.delivery_status == "failed"
            await session.refresh(event)
            assert event.status == "dead_letter" and event.retry_count == 3
            await service.submit_procurement_request(company_id=company_id, procurement_request_id=request_id, actor_user_id=None)
            assert event.event_id == event_id and event.status == "pending" and event.retry_count == 0
            assert submitted.delivery_status == "sending"
            now = datetime.now(UTC)
            def update(status, occurred_at):
                return EventEnvelope(event_id=uuid4(), event_type="erp.procurement.request.updated.v1", event_version=1,
                    company_id=company_id, aggregate_id=request_id, aggregate_type="construction_procurement_request",
                    occurred_at=occurred_at, producer="erp-api", correlation_id=uuid4(), causation_id=None,
                    payload={"source_id": str(request_id), "source_revision": submitted.submission_revision,
                        "external_procurement_id": str(uuid4()), "external_procurement_status": status,
                        "order_numbers": ["12"], "orders": [{"number": "12", "status": "OPEN"}],
                        "items": [{"sequence_number": 1, "quantity": "10", "qty_ordered": "4", "qty_available": "6"}]})
            approved = update("APPROVED", now)
            await service.apply_procurement_updated_event(event=approved)
            await service.apply_procurement_updated_event(event=approved)
            await service.apply_procurement_updated_event(event=update("PENDING_APPROVAL", now - timedelta(seconds=1)))
            assert submitted.status == "approved" and submitted.external_items[0]["qty_available"] == "6"
            assert submitted.external_orders[0]["number"] == "12"
    finally:
        async with factory() as session:
            await session.execute(delete(ProcessedEvent).where(ProcessedEvent.company_id == company_id))
            await session.execute(delete(DeadLetterEvent).where(DeadLetterEvent.company_id == company_id))
            await session.execute(delete(OutboxEvent).where(OutboxEvent.company_id == company_id))
            await session.execute(delete(ConstructionProject).where(ConstructionProject.id == project_id))
            await session.commit()
        await engine.dispose()
