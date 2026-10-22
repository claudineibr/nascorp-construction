from datetime import UTC, datetime, timedelta

from app.domain.services.construction_project_service import ConstructionProjectService
from app.domain.services.subcontract_service import SubcontractService
from app.infrastructure.clients.erp_construction import ErpConstructionClient
from app.infrastructure.database.session import AsyncSessionLocal
from app.infrastructure.events.outbox_relay import DatabaseOutboxRelay
from app.infrastructure.repository.construction_repository import ConstructionRepository
from app.infrastructure.repository.event_repository import EventRepository
from app.infrastructure.repository.subcontract_repository import SubcontractRepository


async def relay_subcontract_measurements():
    async with AsyncSessionLocal() as session:
        events = EventRepository(session)
        repository = ConstructionRepository(session)
        client = ErpConstructionClient()
        for _ in range(30):
            row = await events.claim_contract_measurement(datetime.now(UTC))
            if row is None:
                break
            row_id, owner = row.id, row.lease_owner
            envelope = DatabaseOutboxRelay(repository=events, publisher=None)._to_envelope(row)
            try:
                response = await client.cancel_measurement_payable(company_id=envelope.company_id,
                    measurement_id=envelope.aggregate_id, user_id=envelope.payload.get("user_id"),
                    reason=envelope.payload["reason"])
                measurement = await SubcontractRepository(session).measurement(envelope.company_id, envelope.aggregate_id, True)
                row = await events.leased_event(row_id)
                if row.lease_owner != owner:
                    await session.rollback()
                    continue
                if measurement is not None and measurement.approval_cycle == envelope.payload.get("approval_cycle"):
                    if response.get("status") != "CANCELED":
                        raise ValueError("O ERP não confirmou o cancelamento financeiro.")
                    await SubcontractService(ConstructionProjectService(repository=repository)).reverse_consumption(
                        measurement, envelope.payload.get("user_id"))
                    measurement.status, measurement.reversal_pending = "rejected", False
                    measurement.external_accounts_payable_id = None
                    measurement.external_accounts_payable_shared = False
                    measurement.rejection_reason = envelope.payload["reason"]
                await events.mark_published(row)
                row.lease_owner, row.lease_until = None, None
                await session.commit()
            except Exception as exc:
                await session.rollback()
                row = await events.leased_event(row_id)
                if row is not None and row.lease_owner == owner:
                    if row.retry_count + 1 >= 3:
                        await events.move_to_dead_letter(row, str(exc))
                    else:
                        await events.mark_failed(row, str(exc))
                        row.next_attempt_at = datetime.now(UTC) + timedelta(seconds=15 * 2 ** row.retry_count)
                    row.lease_owner, row.lease_until = None, None
                    await session.commit()
