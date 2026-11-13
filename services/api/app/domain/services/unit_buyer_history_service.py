import logging
from uuid import uuid4

import httpx

from app.domain.constants import ConstructionUnitStatus
from app.domain.exceptions import ConstructionDomainError, ConstructionInvalidValueError
from app.domain.unit_description import original_unit_description, occupied_unit_description
from app.infrastructure.database.models.unit_buyer_history import ConstructionUnitBuyerHistory

logger = logging.getLogger(__name__)


class UnitBuyerHistoryService:
    async def list_unit_buyer_history(self, company_id, unit_id):
        await self._get_unit(company_id=company_id, unit_id=unit_id)
        return await self.repository.unit_buyer_history(company_id, unit_id)

    async def _compose_unit_description(self, unit, buyer_id, actor_user_id, base_override=None):
        project = await self.repository.get_project(company_id=unit.company_id, project_id=unit.project_id)
        if project is None:
            raise ConstructionInvalidValueError(message='A obra da unidade não foi encontrada nesta empresa.')
        rows = await self.repository.unit_buyer_history(unit.company_id, unit.id)
        names = {}
        for row in rows:
            if row.buyer_name:
                names[row.buyer_person_id] = row.buyer_name
        cache = getattr(self, '_unit_person_names', {})
        for person_id in dict.fromkeys([unit.buyer_person_id, buyer_id]):
            if person_id is None or self.erp_client is None:
                continue
            key = (unit.company_id, person_id)
            if key not in cache:
                cache[key] = await self.erp_client.get_person_name(
                    company_id=unit.company_id, user_id=actor_user_id, person_id=person_id,
                )
                self._unit_person_names = cache
            if cache[key]:
                names[person_id] = cache[key]
        buyer_name = names.get(buyer_id)
        if buyer_id is not None and not buyer_name:
            raise ConstructionInvalidValueError(
                message='Não foi possível conferir o nome do comprador. Tente novamente antes de concluir.',
            )
        previous_name = names.get(unit.buyer_person_id)
        if unit.buyer_person_id is None:
            previous_name = next((row.buyer_name for row in reversed(rows) if row.buyer_name), None)
        base = unit.original_description
        if base_override is not None or base is None:
            base = original_unit_description(
                base_override if base_override is not None else unit.description, previous_name, project.name,
            )
        description = occupied_unit_description(base, buyer_name.upper(), project.name) if buyer_id else base
        return base, description, buyer_name

    async def _rename_unit_cost_center(self, unit, description, actor_user_id):
        if (not description or unit.analytic_cost_center_id is None or self.erp_client is None
                or actor_user_id is None):
            return False
        try:
            await self.erp_client.rename_unit_description(
                company_id=unit.company_id, user_id=actor_user_id,
                cost_center_id=unit.analytic_cost_center_id, description=description,
            )
        except httpx.HTTPStatusError as error:
            raise self._erp_domain_error(
                request_error=error, fallback_message='Não foi possível atualizar o nome da unidade no ERP.',
            ) from error
        except httpx.RequestError as error:
            logger.info(f'[unit_name] erp_indisponivel: unit_id={unit.id} cost_center_id={unit.analytic_cost_center_id}')
            raise ConstructionDomainError(
                message='O ERP está indisponível. Tente novamente para atualizar o nome da unidade.',
                status_code=503, error_code='CONSTRUCTION_ERP_UNAVAILABLE',
            ) from error
        logger.info(f'[unit_name] centro_renomeado: unit_id={unit.id} cost_center_id={unit.analytic_cost_center_id}')
        return True

    async def _rename_unit_cost_center_for_buyer(self, unit, buyer_id, actor_user_id):
        _, description, _ = await self._compose_unit_description(unit, buyer_id, actor_user_id)
        if description == unit.description:
            return False
        return await self._rename_unit_cost_center(unit, description, actor_user_id)

    async def _restore_unit_cost_center_name(self, unit, description, actor_user_id):
        try:
            await self._rename_unit_cost_center(unit, description, actor_user_id)
        except ConstructionDomainError as error:
            logger.warning(
                f'[unit_name] restauracao_falhou: unit_id={unit.id} cost_center_id={unit.analytic_cost_center_id} '
                f'erro={error.error_code}'
            )

    async def _sync_unit_buyer_description(self, unit, buyer_id, actor_user_id, sync_cost_center=False,
                                          base_override=None):
        base, description, buyer_name = await self._compose_unit_description(
            unit, buyer_id, actor_user_id, base_override,
        )
        if sync_cost_center and description != unit.description:
            await self._rename_unit_cost_center(unit, description, actor_user_id)
        if unit.buyer_person_id != buyer_id and (
            unit.client_situation is not None or unit.client_situation_date is not None
        ):
            unit.client_situation = None
            unit.client_situation_date = None
            logger.info(
                f'[unit_tracking] situacao_cliente_limpa: company_id={unit.company_id} '
                f'unit_id={unit.id} actor_id={actor_user_id}'
            )
        unit.original_description = base
        unit.description = description
        logger.info(f'[unit_name] atualizado: unit_id={unit.id} buyer_id={buyer_id} sync_cost_center={sync_cost_center}')
        return buyer_name

    async def _sync_unit_buyer_history(self, unit, buyer_id, instant, actor_user_id, reason, sync_cost_center=False):
        buyer_name = await self._sync_unit_buyer_description(unit, buyer_id, actor_user_id, sync_cost_center)
        rows = await self.repository.unit_buyer_history(unit.company_id, unit.id, open_only=True)
        if buyer_id is not None and unit.buyer_person_id == buyer_id:
            if any(row.buyer_person_id == buyer_id for row in rows):
                return
            if unit.status in (ConstructionUnitStatus.SOLD, ConstructionUnitStatus.DELIVERED):
                if unit.sold_at is None:
                    logger.info(f'[unit_buyer_history] sem_data_da_venda: unit_id={unit.id} buyer_id={buyer_id}')
                    return
                await self.repository.add(ConstructionUnitBuyerHistory(
                    company_id=unit.company_id, unit_id=unit.id, buyer_person_id=buyer_id, buyer_name=buyer_name,
                    included_at=unit.sold_at, source_id=f'native:{uuid4()}',
                ))
                logger.info(f'[unit_buyer_history] passagem_da_venda_vigente: unit_id={unit.id} buyer_id={buyer_id}')
                return
        person_id = self.repository.session.info.get('actor_person_id')
        cache = getattr(self, '_buyer_history_names', {})
        if person_id not in cache:
            cache[person_id] = await self._resolve_actor_name(
                company_id=unit.company_id, actor_user_id=actor_user_id, actor_person_id=person_id,
            )
            self._buyer_history_names = cache
        actor_name = cache[person_id]
        for row in rows:
            row.excluded_at = instant
            row.excluded_by_user_id = actor_user_id
            row.excluded_by_name = actor_name
            logger.info(f'[unit_buyer_history] saida: unit_id={unit.id} row_id={row.id} motivo={reason}')
        if buyer_id is not None:
            await self.repository.add(ConstructionUnitBuyerHistory(
                company_id=unit.company_id, unit_id=unit.id, buyer_person_id=buyer_id, buyer_name=buyer_name,
                included_at=instant, included_by_user_id=actor_user_id, included_by_name=actor_name,
                source_id=f'native:{uuid4()}', reason=reason,
            ))
        logger.info(f'[unit_buyer_history] atualizado: unit_id={unit.id} buyer_id={buyer_id} actor={actor_user_id}')
