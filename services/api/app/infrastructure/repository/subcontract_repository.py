from sqlalchemy import func, select, text

from app.infrastructure.database.models import ConstructionMeasurement, ConstructionMeasurementItem
from app.infrastructure.database.models.subcontract import ConstructionSubcontract, ConstructionSubcontractItem, ConstructionSubcontractVersion, ConstructionSubcontractConsumption, ConstructionSubcontractDirectBill, ConstructionSubcontractDeduction
from app.infrastructure.repository._project_scope_filters import scope_conditions


class SubcontractRepository:
    def __init__(self, session, scope=None):
        self.session, self.scope = session, scope

    async def lock_code(self, company_id, project_id, code):
        await self.session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
            {"key": f"subcontract:{company_id}:{project_id}:{code.casefold()}"})

    async def by_code(self, company_id, project_id, code):
        return await self.session.scalar(select(ConstructionSubcontract).where(
            ConstructionSubcontract.company_id == company_id, ConstructionSubcontract.project_id == project_id,
            func.lower(ConstructionSubcontract.code) == code.lower()))

    async def get(self, company_id, contract_id, lock=False):
        query = select(ConstructionSubcontract).where(ConstructionSubcontract.company_id == company_id,
            ConstructionSubcontract.id == contract_id, *scope_conditions(ConstructionSubcontract, self.scope))
        return await self.session.scalar(query.with_for_update().execution_options(populate_existing=True) if lock else query)

    async def list(self, company_id, project_id):
        return (await self.session.scalars(select(ConstructionSubcontract).where(
            ConstructionSubcontract.company_id == company_id, ConstructionSubcontract.project_id == project_id,
            *scope_conditions(ConstructionSubcontract, self.scope)).order_by(ConstructionSubcontract.code))).all()

    async def items(self, company_id, contract_id, lock=False):
        query = select(ConstructionSubcontractItem).where(ConstructionSubcontractItem.company_id == company_id,
            ConstructionSubcontractItem.contract_id == contract_id,
            *scope_conditions(ConstructionSubcontractItem, self.scope)).order_by(ConstructionSubcontractItem.id)
        return (await self.session.scalars(query.with_for_update().execution_options(populate_existing=True) if lock else query)).all()

    async def version(self, company_id, contract_id, number):
        return await self.session.scalar(select(ConstructionSubcontractVersion).where(
            ConstructionSubcontractVersion.company_id == company_id, ConstructionSubcontractVersion.contract_id == contract_id,
            ConstructionSubcontractVersion.version_number == number,
            *scope_conditions(ConstructionSubcontractVersion, self.scope)))

    async def version_by_id(self, company_id, contract_id, version_id):
        return await self.session.scalar(select(ConstructionSubcontractVersion).where(
            ConstructionSubcontractVersion.company_id == company_id, ConstructionSubcontractVersion.contract_id == contract_id,
            ConstructionSubcontractVersion.id == version_id, *scope_conditions(ConstructionSubcontractVersion, self.scope)))

    async def measurement(self, company_id, measurement_id, lock=False):
        query = select(ConstructionMeasurement).where(ConstructionMeasurement.company_id == company_id,
            ConstructionMeasurement.id == measurement_id, *scope_conditions(ConstructionMeasurement, self.scope))
        return await self.session.scalar(query.with_for_update().execution_options(populate_existing=True) if lock else query)

    async def measurement_items(self, company_id, measurement_id):
        return (await self.session.scalars(select(ConstructionMeasurementItem).where(
            ConstructionMeasurementItem.company_id == company_id, ConstructionMeasurementItem.measurement_id == measurement_id,
            *scope_conditions(ConstructionMeasurementItem, self.scope)).order_by(ConstructionMeasurementItem.id))).all()

    async def consumptions(self, company_id, measurement_id, active_only=True):
        conditions = [ConstructionSubcontractConsumption.company_id == company_id,
            ConstructionSubcontractConsumption.measurement_id == measurement_id,
            *scope_conditions(ConstructionSubcontractConsumption, self.scope)]
        if active_only:
            conditions.append(ConstructionSubcontractConsumption.status == "POSTED")
        return (await self.session.scalars(select(ConstructionSubcontractConsumption).where(*conditions)
            .order_by(ConstructionSubcontractConsumption.id).with_for_update())).all()

    async def item_has_history(self, company_id, item_id):
        return await self.session.scalar(select(ConstructionSubcontractConsumption.id).where(
            ConstructionSubcontractConsumption.company_id == company_id,
            ConstructionSubcontractConsumption.measurement_item_id == item_id).limit(1)) is not None

    async def direct_bills(self, company_id, contract_id, lock=False):
        query = select(ConstructionSubcontractDirectBill).where(ConstructionSubcontractDirectBill.company_id == company_id,
            ConstructionSubcontractDirectBill.contract_id == contract_id,
            ConstructionSubcontractDirectBill.status == "ACTIVE",
            *scope_conditions(ConstructionSubcontractDirectBill, self.scope)).order_by(ConstructionSubcontractDirectBill.id)
        return (await self.session.scalars(query.with_for_update().execution_options(populate_existing=True) if lock else query)).all()

    async def direct_bill_by_document(self, company_id, document_id):
        return await self.session.scalar(select(ConstructionSubcontractDirectBill).where(
            ConstructionSubcontractDirectBill.company_id == company_id,
            ConstructionSubcontractDirectBill.status == "ACTIVE",
            ConstructionSubcontractDirectBill.payable_document_id == document_id))

    async def lock_direct_bill_document(self, company_id, document_id):
        await self.session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
            {"key": f"subcontract-direct-bill:{company_id}:{document_id}"})

    async def bill_has_open_deductions(self, company_id, bill_id):
        return await self.session.scalar(select(ConstructionSubcontractDeduction.id).where(
            ConstructionSubcontractDeduction.company_id == company_id, ConstructionSubcontractDeduction.direct_bill_id == bill_id,
            ConstructionSubcontractDeduction.status.in_(["DRAFT", "POSTED"])).limit(1)) is not None

    async def deductions(self, company_id, measurement_id):
        return (await self.session.scalars(select(ConstructionSubcontractDeduction).where(
            ConstructionSubcontractDeduction.company_id == company_id,
            ConstructionSubcontractDeduction.measurement_id == measurement_id,
            *scope_conditions(ConstructionSubcontractDeduction, self.scope))
            .order_by(ConstructionSubcontractDeduction.direct_bill_id).with_for_update())).all()
