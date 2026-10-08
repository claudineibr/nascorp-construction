import asyncio
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.domain.exceptions import ConstructionDomainError, ConstructionNotFoundError
from app.domain.services.construction_project_service import ConstructionProjectService
from app.domain.services.subcontract_service import SubcontractService
from app.infrastructure.database.models import ConstructionProject, ConstructionMeasurement, ConstructionMeasurementItem
from app.infrastructure.database.models.subcontract import ConstructionSubcontract, ConstructionSubcontractItem, ConstructionSubcontractVersion, ConstructionSubcontractConsumption, ConstructionSubcontractDirectBill, ConstructionSubcontractDeduction
from app.infrastructure.repository.construction_repository import ConstructionRepository
from app.schemas.construction.subcontract import SubcontractRequest, SubcontractDirectBillRequest, SubcontractDeductionRequest
from tests.integration_database import create_reachable_engine_or_skip


async def setup(session, company_id):
    project = ConstructionProject(id=uuid4(), company_id=company_id, code=f"TEST-{uuid4().hex[:10]}", name="Contract test", status="planning", project_type="condominium")
    session.add(project)
    await session.commit()
    supplier = uuid4()
    client = AsyncMock()
    client.list_person_summaries.return_value = {"items": [{"id": str(supplier), "name": "Empreiteiro"}]}
    service = SubcontractService(ConstructionProjectService(repository=ConstructionRepository(session), erp_client=client))
    contract = await service.save(company_id, project.id, SubcontractRequest(code="CT-1", title="Alvenaria",
        supplier_person_id=supplier, valid_from=date.today() - timedelta(days=1), valid_to=date.today() + timedelta(days=60),
        items=[{"description": "Parede", "unit_of_measure": "M2", "quantity": "10", "material_unit_price": "2", "labor_unit_price": "3"}]), uuid4())
    contract = await service.release(company_id, contract["id"], uuid4())
    return service, project, supplier, contract


async def measurement(session, service, company_id, project, supplier, contract, quantity, code):
    parent = ConstructionMeasurement(id=uuid4(), company_id=company_id, project_id=project.id, code=code,
        subcontract_id=contract["id"], competence_date=date.today(), measured_amount=Decimal("30"), gross_amount=Decimal("30"),
        retentions_amount=Decimal("0"), due_date=date.today(), supplier_person_id=supplier, status="submitted",
        document_type="NFS-e", document_number=code, retention_details=[])
    session.add(parent)
    await session.flush()
    item = ConstructionMeasurementItem(id=uuid4(), company_id=company_id, measurement_id=parent.id,
        sequence_number=1, description="Parede", amount=Decimal("30"))
    await service.bind_item(parent, item, contract["items"][0]["id"], Decimal(quantity))
    session.add(item)
    await session.commit()
    return parent


async def cleanup(factory, company_id):
    async with factory() as session:
        for model in [ConstructionSubcontractDeduction, ConstructionSubcontractConsumption, ConstructionSubcontractDirectBill,
            ConstructionMeasurementItem, ConstructionMeasurement, ConstructionSubcontractVersion, ConstructionSubcontractItem,
            ConstructionSubcontract, ConstructionProject]:
            await session.execute(delete(model).where(model.company_id == company_id))
        await session.commit()


@pytest.mark.asyncio
async def test_concurrent_measurements_cannot_exceed_contract_and_reversal_restores_exact_quantity():
    engine = await create_reachable_engine_or_skip()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    company_id = uuid4()
    try:
        async with factory() as session:
            service, project, supplier, contract = await setup(session, company_id)
            first = await measurement(session, service, company_id, project, supplier, contract, "6", "M1")
            second = await measurement(session, service, company_id, project, supplier, contract, "6", "M2")
        async def approve(measurement_id):
            async with factory() as session:
                service = SubcontractService(ConstructionProjectService(repository=ConstructionRepository(session)))
                row = await service.repository.measurement(company_id, measurement_id, True)
                try:
                    await service.consume(row)
                    await session.commit()
                    return True
                except ConstructionDomainError:
                    await session.rollback()
                    return False
        results = await asyncio.gather(approve(first.id), approve(second.id))
        assert sorted(results) == [False, True]
        async with factory() as session:
            item = await session.scalar(select(ConstructionSubcontractItem).where(ConstructionSubcontractItem.company_id == company_id))
            assert item.consumed_quantity == Decimal("6")
            posted = await session.scalar(select(ConstructionSubcontractConsumption).where(ConstructionSubcontractConsumption.company_id == company_id))
            service = SubcontractService(ConstructionProjectService(repository=ConstructionRepository(session)))
            parent = await service.repository.measurement(company_id, posted.measurement_id, True)
            await service.reverse_consumption(parent, uuid4())
            await session.commit()
            assert item.consumed_quantity == 0 and posted.status == "REVERSED"
            await service.reverse_consumption(parent, uuid4())
            await session.commit()
            assert item.consumed_quantity == 0
    finally:
        await cleanup(factory, company_id)
        await engine.dispose()


@pytest.mark.asyncio
async def test_direct_material_credit_posts_once_and_reversal_restores_without_new_erp_document():
    engine = await create_reachable_engine_or_skip()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    company_id = uuid4()
    try:
        async with factory() as session:
            service, project, supplier, contract = await setup(session, company_id)
            parent = await measurement(session, service, company_id, project, supplier, contract, "6", "M1")
            parent.status = "draft"
            await session.commit()
            service.projects.erp_client.get_direct_billing_document.return_value = {
                "id": str(uuid4()), "amount": "10.00", "document_number": "NF-10", "project_id": str(project.id), "company_id": str(company_id)}
            bill = await service.register_direct_bill(company_id, contract["id"],
                SubcontractDirectBillRequest(payable_document_id=uuid4(), amount="10"), uuid4())
            await service.set_deduction(company_id, parent.id, SubcontractDeductionRequest(direct_bill_id=bill["id"], amount="10"))
            assert parent.direct_billing_amount == Decimal("10") and parent.net_amount == Decimal("20")
            parent.status = "submitted"
            await service.consume(parent)
            await session.commit()
            credit = await session.get(ConstructionSubcontractDirectBill, bill["id"])
            assert credit.deducted_amount == Decimal("10")
            await service.consume(parent)
            await session.commit()
            assert credit.deducted_amount == Decimal("10")
            await service.reverse_consumption(parent, uuid4())
            await session.commit()
            assert credit.deducted_amount == 0
            discount = await session.scalar(select(ConstructionSubcontractDeduction).where(
                ConstructionSubcontractDeduction.measurement_id == parent.id))
            assert discount.status == "REVERSED"
            service.projects.erp_client.create_accounts_payable_from_measurement.assert_not_awaited()
    finally:
        await cleanup(factory, company_id)
        await engine.dispose()


@pytest.mark.asyncio
async def test_amendment_preserves_measurement_prices_and_rejects_foreign_company():
    engine = await create_reachable_engine_or_skip()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    company_id = uuid4()
    try:
        async with factory() as session:
            service, project, supplier, contract = await setup(session, company_id)
            parent = await measurement(session, service, company_id, project, supplier, contract, "2", "M1")
            original_version = parent.subcontract_version_id
            original = contract["items"][0]
            await service.save(company_id, project.id, SubcontractRequest(
                code="CT-1", title="Alvenaria revisada", supplier_person_id=supplier,
                valid_from=contract["valid_from"], valid_to=contract["valid_to"],
                items=[{"id": original["id"], "description": "Parede", "unit_of_measure": "M2",
                    "quantity": "10", "material_unit_price": "20", "labor_unit_price": "30"}],
            ), uuid4(), contract_id=contract["id"])
            revised = await service.release(company_id, contract["id"], uuid4())
            existing = await session.scalar(select(ConstructionMeasurementItem).where(
                ConstructionMeasurementItem.measurement_id == parent.id))
            await service.bind_item(parent, existing, original["id"], Decimal("3"))
            assert existing.amount == Decimal("15")
            assert parent.subcontract_version_id == original_version
            historical = await service.detail(company_id, contract["id"], original_version)
            assert Decimal(historical["items"][0]["material_unit_price"]) == Decimal("2")
            with pytest.raises(ConstructionNotFoundError):
                await service.detail(company_id, contract["id"], uuid4())
            later = await measurement(session, service, company_id, project, supplier, revised, "2", "M2")
            new_item = await session.scalar(select(ConstructionMeasurementItem).where(
                ConstructionMeasurementItem.measurement_id == later.id))
            assert new_item.amount == Decimal("100")
            assert later.subcontract_version_id != original_version
            with pytest.raises(ConstructionNotFoundError):
                await service.get(uuid4(), contract["id"])
            with pytest.raises(ConstructionDomainError):
                await service.bind_parent(parent, {"supplier_person_id": uuid4()})
    finally:
        await cleanup(factory, company_id)
        await engine.dispose()
