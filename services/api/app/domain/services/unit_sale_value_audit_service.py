from decimal import Decimal
import logging

from app.domain.exceptions import ConstructionInvalidValueError
from app.infrastructure.database.models.unit_sale_value_audit import ConstructionUnitSaleValueAudit


logger = logging.getLogger(__name__)


class UnitSaleValueAuditService:
    def _sale_value_snapshot(self, *, sale_price, discount, sources, documentations, commission_offset):
        def money(value):
            return format(Decimal(str(value or 0)).quantize(Decimal("0.01")), "f")
        snapshot = {"sale_price": money(sale_price) if sale_price is not None else None,
                    "discount_amount": money(discount), "commission_offset": money(commission_offset)}
        for source in ("down_payment", "government_subsidy", "fgts", "financing"):
            snapshot[source] = money(sum((Decimal(str(row["amount"])) for row in sources
                                          if row["source_type"] == source), Decimal("0")))
        snapshot["documentations"] = sorted([
            {"documentation_type_id": str(row["documentation_type_id"]), "name": row["name"],
             "amount": money(row["amount"])} for row in documentations
        ], key=lambda row: row["documentation_type_id"])
        snapshot["documentation_total"] = money(sum(
            (Decimal(row["amount"]) for row in snapshot["documentations"]), Decimal("0"),
        ))
        balance = (Decimal(snapshot["sale_price"] or "0") + Decimal(snapshot["documentation_total"])
                   - Decimal(snapshot["discount_amount"]) - Decimal(snapshot["commission_offset"])
                   - sum((Decimal(snapshot[key]) for key in
                          ("down_payment", "government_subsidy", "fgts", "financing")), Decimal("0")))
        snapshot["balance"] = money(max(balance, Decimal("0"))) if sale_price is not None else None
        snapshot["composition_difference"] = money(max(-balance, Decimal("0"))) if sale_price is not None else None
        return snapshot

    async def _record_sale_value_change(self, *, unit, sale, old_data, new_data, reason,
                                        actor_user_id, actor_person_id, changed_at):
        if old_data == new_data:
            return
        reason = (reason or "").strip()
        if not reason:
            logger.info(f"[sale_value_audit] motivo_ausente: company_id={unit.company_id} unit_id={unit.id} sale_id={sale.id}")
            raise ConstructionInvalidValueError(
                message="Informe o motivo da alteração dos valores da venda.",
                error_code="CONSTRUCTION_SALE_VALUE_CHANGE_REASON_REQUIRED",
            )
        actor_name = None
        if actor_person_id is not None and self.erp_client is not None:
            actor_name = await self.erp_client.get_person_name(
                company_id=unit.company_id, user_id=actor_user_id, person_id=actor_person_id,
            )
        await self.repository.add(ConstructionUnitSaleValueAudit(
            company_id=unit.company_id, unit_id=unit.id, sale_id=sale.id, sale_sequence=sale.sequence,
            actor_user_id=actor_user_id, actor_name=actor_name, reason=reason,
            old_data=old_data, new_data=new_data, changed_at=changed_at,
        ))
        logger.info(f"[sale_value_audit] registro_preparado: company_id={unit.company_id} unit_id={unit.id} sale_id={sale.id} actor_user_id={actor_user_id}")

    async def list_unit_sale_value_audits(self, *, company_id, unit_id, page, page_size, direction):
        await self._get_unit(company_id=company_id, unit_id=unit_id)
        logger.info(f"[sale_value_audit] consultar: company_id={company_id} unit_id={unit_id} page={page}")
        return await self.repository.list_unit_sale_value_audits(
            company_id=company_id, unit_id=unit_id, page=page, page_size=page_size, direction=direction,
        )
