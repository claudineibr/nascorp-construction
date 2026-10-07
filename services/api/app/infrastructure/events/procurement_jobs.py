import asyncio
import logging
import json
from collections import defaultdict
from contextlib import asynccontextmanager, suppress

from app.domain.events.constants import ConstructionEventType
from app.domain.services.construction_project_service import ConstructionProjectService
from app.infrastructure.clients.erp_construction import ErpConstructionClient
from app.infrastructure.database.session import AsyncSessionLocal
from app.infrastructure.events.outbox_relay import DatabaseOutboxRelay
from app.infrastructure.repository.construction_repository import ConstructionRepository
from app.infrastructure.repository.event_repository import EventRepository

logger = logging.getLogger(__name__)


class ProcurementPublisher:
    def __init__(self, session):
        self.repository = ConstructionRepository(session)
        self.events = EventRepository(session)
        self.client = ErpConstructionClient()

    async def publish(self, event):
        request = await self.repository.get_procurement_request(company_id=event.company_id,
            procurement_request_id=event.aggregate_id, lock=True)
        if request is not None and request.delivery_status == "sent" and request.submission_revision == event.payload.get("source_revision"):
            return
        try:
            response = await self.client.deliver_event(event=event)
        except Exception as exc:
            outbox = await self.events.latest_procurement_event(company_id=event.company_id, aggregate_id=event.aggregate_id)
            if request is not None and request.submission_revision == event.payload.get("source_revision"):
                request.delivery_status = "failed" if outbox.retry_count + 1 >= 3 else "sending"
            logger.warning(json.dumps({"event": "procurement_delivery_failed", "event_id": str(event.event_id),
                "company_id": str(event.company_id), "reason": str(exc)}))
            raise
        if request is not None and request.submission_revision == event.payload.get("source_revision"):
            if request.external_snapshot_at is None:
                ConstructionProjectService._apply_procurement_snapshot_from_payload(
                    procurement_request=request, payload=response.payload)
            request.delivery_status = "sent"


async def relay_procurement():
    async with AsyncSessionLocal() as session:
        relay = DatabaseOutboxRelay(repository=EventRepository(session), publisher=ProcurementPublisher(session))
        await relay.relay_pending(event_type=ConstructionEventType.PROCUREMENT_REQUESTED)


async def run_periodically(job, interval):
    while True:
        try:
            await job()
        except Exception:
            logger.exception("procurement_job_failed")
        await asyncio.sleep(interval)


async def reconcile_procurement():
    async with AsyncSessionLocal() as session:
        repository = ConstructionRepository(session)
        service = ConstructionProjectService(repository=repository, erp_client=ErpConstructionClient())
        groups = defaultdict(list)
        for request in await repository.procurement_for_reconciliation():
            groups[request.company_id].append(request)
        for company_id, items in groups.items():
            await service.sync_procurement_statuses(company_id=company_id, actor_user_id=None, items=items)


@asynccontextmanager
async def procurement_lifespan(app):
    tasks = [asyncio.create_task(run_periodically(relay_procurement, 15)),
        asyncio.create_task(run_periodically(reconcile_procurement, 86400))]
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task
