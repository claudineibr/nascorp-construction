import logging
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import httpx

from app.domain.constants import ConstructionUnitStatus
from app.domain.events.constants import (
    ConstructionAggregateType, ConstructionEventType, ConstructionIntegrationMode, EventProducer, EventStatus,
)
from app.domain.events.contracts import EventEnvelope
from app.domain.exceptions import ConstructionInvalidValueError, ConstructionNotFoundError, ConstructionDomainError
from app.infrastructure.database.models import ConstructionUnitSale

logger = logging.getLogger(__name__)

SALE_FIELDS = (
    'buyer_person_id', 'secondary_buyer_person_id', 'broker_person_id', 'sale_price', 'discount_amount',
    'contract_signature_date', 'financing_completed', 'financing_date', 'sale_notes',
    'external_contract_id', 'external_receivable_id', 'external_contract_status', 'external_receivable_status',
)
CONTRACT_FIELDS = ('external_contract_id', 'external_contract_status')
TRANSFERRED_SALE_FIELDS = tuple(key for key in SALE_FIELDS if key not in CONTRACT_FIELDS)


class UnitTransferService:
    async def _editable_transfer_commission(self, company_id, commission_id):
        commission = await self._get_unit_commission(company_id=company_id, commission_id=commission_id)
        unit_id = commission.unit_id
        await self._editable_transfer_unit(company_id, unit_id)
        commission = await self.repository.lock_transfer_commission(company_id, commission_id)
        if commission is None:
            raise ConstructionNotFoundError(resource_name='a comissão no seu acesso')
        if commission.unit_id != unit_id:
            raise ConstructionInvalidValueError(message='A comissão mudou de unidade. Atualize a tela antes de editar.')
        return commission

    async def retry_unit_transfer(self, company_id, unit_id, event_id, actor_user_id):
        event = await self.repository.unit_transfer_event(company_id, event_id)
        if event is None or str(unit_id) not in (str(event.aggregate_id), event.payload['target_unit_id']):
            raise ConstructionNotFoundError(resource_name='a troca de unidade')
        for key in sorted([event.aggregate_id, UUID(event.payload['target_unit_id'])], key=str):
            if await self.repository.lock_unit(company_id=company_id, unit_id=key) is None:
                raise ConstructionNotFoundError(resource_name='as unidades no seu acesso')
        if event.status in (EventStatus.FAILED, EventStatus.DEAD_LETTER):
            event.payload = {**event.payload, 'initiated_by_user_id': event.payload.get('initiated_by_user_id')
                             or event.payload.get('user_id'), 'user_id': str(actor_user_id)}
            event.status = EventStatus.PENDING
            event.retry_count = 0
            event.last_error = None
            event.next_attempt_at = None
            await self.repository.commit()
            logger.info(f'[unit_transfer] retentativa: company_id={company_id} event_id={event_id}')
        return {'status': event.status, 'transfer_id': event.event_id}

    async def _editable_transfer_unit(self, company_id, unit_id):
        unit = await self.repository.lock_unit(company_id=company_id, unit_id=unit_id)
        if unit is None:
            raise ConstructionNotFoundError(resource_name='a unidade')
        await self.require_no_unit_transfer(company_id, unit_id)
        return unit

    async def list_unit_transfer_targets(self, company_id, unit_id, search, page, page_size):
        await self._get_unit(company_id=company_id, unit_id=unit_id)
        return await self.repository.unit_transfer_targets(company_id, unit_id, search, page, page_size)

    async def require_no_unit_transfer(self, company_id, unit_id):
        event = await self.repository.pending_unit_transfer(company_id, unit_id)
        if event is not None:
            raise ConstructionInvalidValueError(
                message='A unidade tem uma troca com integração financeira pendente. Aguarde a conclusão antes de alterar.',
                error_code='CONSTRUCTION_UNIT_TRANSFER_PENDING',
            )

    async def _transfer_units(self, company_id, unit_id, request, actor_user_id):
        if unit_id == request.target_unit_id:
            raise ConstructionInvalidValueError(message='Selecione uma unidade de destino diferente da origem.')
        units = {}
        for key in sorted([unit_id, request.target_unit_id], key=str):
            unit = await self.repository.lock_unit(company_id=company_id, unit_id=key)
            if unit is None:
                raise ConstructionNotFoundError(resource_name='a unidade no seu acesso desta empresa')
            await self.require_no_unit_transfer(company_id, key)
            if await self.repository.pending_sale_integration(company_id, key) is not None:
                raise ConstructionInvalidValueError(
                    message='Aguarde a integração atual da unidade com o ERP antes de fazer a troca.',
                )
            units[key] = unit
        source, target = units[unit_id], units[request.target_unit_id]
        if source.status != ConstructionUnitStatus.SOLD or source.buyer_person_id is None:
            raise ConstructionInvalidValueError(message='A troca exige uma unidade vendida e ainda não entregue.')
        if (target.status != ConstructionUnitStatus.AVAILABLE or target.buyer_person_id is not None
                or target.current_sale_id is not None or target.external_contract_id is not None):
            raise ConstructionInvalidValueError(message='A unidade de destino precisa estar disponível e sem venda ativa.')
        if not source.analytic_cost_center_id or not target.analytic_cost_center_id:
            raise ConstructionInvalidValueError(message='As duas unidades precisam ter centro de custo vinculado.')
        if not source.current_sale_id:
            raise ConstructionInvalidValueError(message='A venda da unidade não possui histórico vinculado. Revise antes da troca.')
        if request.source_sale_id is not None and request.source_sale_id != source.current_sale_id:
            raise ConstructionInvalidValueError(message='A venda foi alterada. Abra a troca novamente para conferir.')
        sale = await self.repository.get_unit_sale(company_id=company_id, sale_id=source.current_sale_id, lock=True)
        if sale is None or sale.status != 'ACTIVE' or sale.unit_id != source.id:
            raise ConstructionInvalidValueError(message='A venda atual não está ativa para transferência.')
        await self._require_company_people(company_id=company_id, actor_user_id=actor_user_id, people={
            'O comprador': source.buyer_person_id, 'O segundo comprador': source.secondary_buyer_person_id,
            'O corretor': source.broker_person_id,
        })
        prior_buyer_sale = await self.repository.has_prior_buyer_sale(company_id, source.id, sale.id, source.buyer_person_id)
        return source, target, sale, prior_buyer_sale

    @staticmethod
    def _transfer_payload(source, target, sale, reason):
        return {
            'source_unit_id': str(source.id), 'target_unit_id': str(target.id),
            'source_sale_id': str(sale.id),
            'source_cost_center_id': str(source.analytic_cost_center_id),
            'target_cost_center_id': str(target.analytic_cost_center_id),
            'buyer_person_id': str(source.buyer_person_id),
            'contract_id': str(source.external_contract_id) if source.external_contract_id else None,
            'source_label': f'{source.code} - {source.description or ""}'[:200],
            'target_label': f'{target.code} - {target.description or ""}'[:200],
            'target_code': target.code,
            'reason': reason.strip(),
        }

    async def _preview_transfer_financial(self, company_id, unit_id, actor_user_id, payload, fallback_message):
        try:
            return await self.erp_client.preview_unit_transfer(
                company_id=company_id, user_id=actor_user_id, payload=payload,
            )
        except httpx.HTTPStatusError as error:
            raise self._erp_domain_error(request_error=error, fallback_message=fallback_message) from error
        except httpx.RequestError as error:
            logger.info(f'[unit_transfer] erp_indisponivel: company_id={company_id} unit_id={unit_id}')
            raise ConstructionDomainError(message='O ERP está indisponível. A troca não foi registrada. Tente novamente.',
                                          status_code=503, error_code='CONSTRUCTION_ERP_UNAVAILABLE') from error

    async def preview_unit_transfer(self, company_id, unit_id, request, actor_user_id):
        try:
            source, target, sale, prior_buyer_sale = await self._transfer_units(company_id, unit_id, request, actor_user_id)
            payload = self._transfer_payload(source, target, sale, request.reason)
            payload['has_prior_buyer_sales'] = prior_buyer_sale
            financial = await self._preview_transfer_financial(
                company_id, unit_id, actor_user_id, payload, 'Não foi possível conferir o financeiro da troca.',
            )
            return {**payload, 'status': 'preview', 'financial': financial}
        finally:
            await self.repository.rollback()

    async def transfer_unit(self, company_id, unit_id, request, actor_user_id):
        logger.info(f'[unit_transfer] iniciar: company_id={company_id} unit_id={unit_id} target={request.target_unit_id}')
        source, target, sale, prior_buyer_sale = await self._transfer_units(company_id, unit_id, request, actor_user_id)
        payload = self._transfer_payload(source, target, sale, request.reason)
        payload['has_prior_buyer_sales'] = prior_buyer_sale
        financial = await self._preview_transfer_financial(
            company_id, unit_id, actor_user_id, payload, 'O financeiro recusou a troca de unidade.',
        )
        instant = datetime.now(UTC)
        event_id = uuid4()
        payload['previous_descriptions'] = {'source': source.description, 'target': target.description}
        await self._sync_unit_buyer_history(source, None, instant, actor_user_id, request.reason)
        await self._sync_unit_buyer_history(
            target, source.buyer_person_id, instant, actor_user_id, request.reason,
        )
        payload['source_description'] = source.description[:255]
        payload['target_description'] = target.description[:255]
        payload['target_label'] = f'{target.code} - {target.description}'[:200]
        payload['source_snapshot'] = self._json_safe({key: getattr(source, key) for key in SALE_FIELDS})
        payload['target_snapshot'] = self._json_safe({key: getattr(target, key) for key in SALE_FIELDS})
        new_sale = ConstructionUnitSale(
            id=uuid4(), company_id=company_id, unit_id=target.id,
            sequence=await self.repository.next_unit_sale_sequence(company_id=company_id, unit_id=target.id),
            status='ACTIVE', source=sale.source, created_by_user_id=actor_user_id,
            sold_at=instant, payment_sources=sale.payment_sources, documentations=sale.documentations,
            termination_terms=sale.termination_terms, transferred_from_sale_id=sale.id,
            **{key: getattr(source, key) for key in TRANSFERRED_SALE_FIELDS},
        )
        sale.status = 'TRANSFERRED'
        sale.paid_amount = Decimal(str(financial['paid_amount']))
        sale.transferred_at = instant
        sale.transferred_to_unit_id = target.id
        await self.repository.add(new_sale)
        await self.repository.flush()
        payload['target_sale_id'] = str(new_sale.id)
        payload['user_id'] = str(actor_user_id) if actor_user_id else None
        payload['source_project_id'] = str(source.project_id)
        payload['target_project_id'] = str(target.project_id)
        payload['financial_preview'] = financial
        payload['commissions'] = await self.repository.transfer_unit_children(
            company_id, source, target, sale.id, new_sale.id,
        )
        for key in TRANSFERRED_SALE_FIELDS:
            setattr(target, key, getattr(source, key))
        for key in CONTRACT_FIELDS:
            setattr(target, key, None)
        logger.info(f'[unit_transfer] contrato_destino_aguarda_erp: source={unit_id} target={target.id}')
        target.current_sale_id = new_sale.id
        target.status = ConstructionUnitStatus.SOLD
        target.sold_at = instant
        target.reserved_at = None
        target.reservation_expires_at = None
        if source.sold_at is not None:
            source.cost_sale_history = [*(source.cost_sale_history or []), {
                'sold_at': source.sold_at.isoformat(), 'terminated_at': instant.isoformat(),
                'reason': 'unit_transfer', 'target_unit_id': str(target.id),
            }]
        for key in SALE_FIELDS:
            if key != 'sale_price':
                setattr(source, key, False if key == 'financing_completed' else None)
        source.current_sale_id = None
        source.sold_at = None
        source.status = ConstructionUnitStatus.AVAILABLE
        source.reserved_at = None
        source.reservation_expires_at = None
        event = EventEnvelope(
            event_id=event_id, event_type=ConstructionEventType.UNIT_TRANSFERRED, event_version=1,
            company_id=company_id, aggregate_id=source.id, aggregate_type=ConstructionAggregateType.UNIT,
            occurred_at=instant, producer=EventProducer.CONSTRUCTION_API, correlation_id=event_id,
            causation_id=None, payload=payload,
        )
        if self.event_repository is None:
            raise ConstructionInvalidValueError(message='A troca exige integração persistente com o financeiro.')
        await self.event_repository.add_outbox_event(event=event, delivery_mode=ConstructionIntegrationMode.SYNC_HTTP)
        await self.repository.commit()
        logger.info(f'[unit_transfer] pendente_integracao: event_id={event_id} source={unit_id} target={target.id}')
        return {**payload, 'transfer_id': event_id, 'status': 'pending', 'occurred_at': instant, 'financial': financial}

    async def list_unit_transfers(self, company_id, unit_id):
        await self._get_unit(company_id=company_id, unit_id=unit_id)
        events = await self.repository.unit_transfer_history(company_id, unit_id)
        return [{
            'transfer_id': row.event_id, 'source_unit_id': row.payload['source_unit_id'],
            'source_sale_id': row.payload['source_sale_id'],
            'target_unit_id': row.payload['target_unit_id'], 'source_label': row.payload['source_label'],
            'target_label': row.payload['target_label'], 'reason': row.payload['reason'],
            'status': row.status, 'occurred_at': row.occurred_at,
            'financial': {},
        } for row in events]
