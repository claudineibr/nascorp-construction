import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.domain.events.constants import ConstructionEventType, EventStatus
from app.domain.services.construction_project_service import ConstructionProjectService
from app.infrastructure.clients.erp_construction import ErpConstructionClient
from app.infrastructure.database.models import OutboxEvent
from app.infrastructure.database.session import AsyncSessionLocal
from app.infrastructure.events.outbox_relay import DatabaseOutboxRelay
from app.infrastructure.repository.construction_repository import ConstructionRepository
from app.infrastructure.repository.event_repository import EventRepository


logger = logging.getLogger(__name__)


async def relay_integration_once(session, client):
    events = EventRepository(session)
    row = await events.next_integration_event()
    if row is None:
        return False

    row_id = row.id
    try:
        if row.delivery_mode == 'legacy':
            await events.move_to_dead_letter(row, 'Evento anterior ao controle de entrega: revisar antes de reenviar para não reaplicar uma operação já confirmada.')
        elif row.event_type == ConstructionEventType.MEASUREMENT_APPROVED:
            await events.move_to_dead_letter(row, 'Aprovação de medição usa vínculo financeiro manual; evento legado exige revisão.')
        else:
            envelope = DatabaseOutboxRelay(repository=events, publisher=None)._to_envelope(row)
            service = ConstructionProjectService(repository=ConstructionRepository(session))
            await service.assert_integration_delivery(envelope)
            response = await client.deliver_event(event=envelope)
            await service.apply_integration_response(request_event=envelope, response_event=response)
            await events.mark_published(row)

        await session.commit()
        logger.info(f"[construction_relay] completed: outbox_id={row_id}")
    except Exception as exc:
        await session.rollback()
        row = await session.scalar(select(OutboxEvent).where(OutboxEvent.id == row_id).with_for_update())
        if row is None or row.status == EventStatus.PUBLISHED:
            await session.rollback()
            return True

        if row.retry_count + 1 >= 3:
            await events.move_to_dead_letter(row, str(exc))
        else:
            await events.mark_failed(row, str(exc))
            row.next_attempt_at = datetime.now(UTC) + timedelta(seconds=15 * 2 ** row.retry_count)

        await session.commit()
        logger.warning(f"[construction_relay] failed: outbox_id={row_id} error={exc}")

    return True


async def relay_integrations():
    async with AsyncSessionLocal() as session:
        for _ in range(30):
            if not await relay_integration_once(session, ErpConstructionClient()):
                break
