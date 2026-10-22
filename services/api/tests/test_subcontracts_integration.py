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
from app.infrastructure.database.models import ConstructionProject, ConstructionMeasurement, ConstructionMeasurementItem, ConstructionProjectServiceTemplate, ConstructionServiceTemplate
from app.infrastructure.database.models.subcontract import ConstructionSubcontract, ConstructionSubcontractItem, ConstructionSubcontractVersion, ConstructionSubcontractConsumption, ConstructionSubcontractDirectBill, ConstructionSubcontractDeduction, ConstructionSubcontractPayable
from app.infrastructure.repository.construction_repository import ConstructionRepository
from app.schemas.construction.project import ConstructionMeasurementUpdate
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
    item = ConstructionMeasurementItem(company_id=company_id, measurement_id=parent.id,
        sequence_number=1, description="Parede", amount=Decimal("30"))
    await service.bind_item(parent, item, contract["items"][0]["id"], Decimal(quantity))
    session.add(item)
    await session.commit()
    return parent


async def cleanup(factory, company_id):
    async with factory() as session:
        for model in [ConstructionSubcontractPayable, ConstructionSubcontractDeduction, ConstructionSubcontractConsumption, ConstructionSubcontractDirectBill,
            ConstructionMeasurementItem, ConstructionMeasurement, ConstructionSubcontractVersion, ConstructionSubcontractItem,
            ConstructionSubcontract, ConstructionProjectServiceTemplate, ConstructionServiceTemplate, ConstructionProject]:
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
            service.projects.erp_client.deliver_event.assert_not_awaited()
    finally:
        await cleanup(factory, company_id)
        await engine.dispose()


@pytest.mark.asyncio
async def test_reversal_without_linked_title_restores_contract_balance_immediately():
    engine = await create_reachable_engine_or_skip()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    company_id = uuid4()
    try:
        async with factory() as session:
            service, project, supplier, contract = await setup(session, company_id)
            parent = await measurement(session, service, company_id, project, supplier, contract, "6", "M1")
            await service.consume(parent)
            parent.status = "approved"
            await session.commit()

            result = await service.request_reversal(company_id, parent.id, "Medição lançada em duplicidade", uuid4())

            assert result["reversal_pending"] is False
            item = await session.scalar(select(ConstructionSubcontractItem).where(ConstructionSubcontractItem.company_id == company_id))
            assert item.consumed_quantity == 0
            assert parent.status == "rejected" and parent.rejection_reason == "Medição lançada em duplicidade"
            assert parent.reversal_pending is False
            service.projects.erp_client.cancel_measurement_payable.assert_not_awaited()
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


@pytest.mark.asyncio
async def test_competence_outside_contract_validity_is_rejected_on_save():
    engine = await create_reachable_engine_or_skip()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    company_id = uuid4()
    try:
        async with factory() as session:
            service, project, supplier, contract = await setup(session, company_id)
            project_id = project.id
            parent = await measurement(session, service, company_id, project, supplier, contract, "2", "M1")
            parent.status = "draft"
            await session.commit()
            parent_id = parent.id
            with pytest.raises(ConstructionDomainError) as error:
                await service.projects.update_measurement(company_id=company_id, measurement_id=parent_id,
                    request=ConstructionMeasurementUpdate(competence_date=date.today() + timedelta(days=90)))
            assert error.value.error_code == "CONSTRUCTION_MEASUREMENT_COMPETENCE_OUT_OF_CONTRACT"
            await session.rollback()
            updated = await service.projects.update_measurement(company_id=company_id, measurement_id=parent_id,
                request=ConstructionMeasurementUpdate(competence_date=date.today()))
            assert updated.competence_date == date.today()

            later = await service.save(company_id, project_id, SubcontractRequest(code="CT-2", title="Reboco",
                supplier_person_id=supplier, valid_from=date.today() + timedelta(days=30),
                valid_to=date.today() + timedelta(days=120),
                items=[{"description": "Reboco", "unit_of_measure": "M2", "quantity": "5", "material_unit_price": "1", "labor_unit_price": "1"}]), uuid4())
            later = await service.release(company_id, later["id"], uuid4())
            legacy = ConstructionMeasurement(id=uuid4(), company_id=company_id, project_id=project_id, code="M2",
                subcontract_id=contract["id"], competence_date=None, measured_amount=Decimal("0"), gross_amount=Decimal("0"),
                retentions_amount=Decimal("0"), due_date=date.today(), supplier_person_id=supplier, status="draft",
                retention_details=[])
            session.add(legacy)
            await session.commit()
            legacy_id = legacy.id
            with pytest.raises(ConstructionDomainError) as missing:
                await service.projects.update_measurement(company_id=company_id, measurement_id=legacy_id,
                    request=ConstructionMeasurementUpdate(description="Ajuste"))
            assert missing.value.error_code == "CONSTRUCTION_MEASUREMENT_COMPETENCE_OUT_OF_CONTRACT"
            await session.rollback()
            with pytest.raises(ConstructionDomainError) as switched:
                await service.projects.update_measurement(company_id=company_id, measurement_id=legacy_id,
                    request=ConstructionMeasurementUpdate(subcontract_id=later["id"], competence_date=date.today()))
            assert switched.value.error_code == "CONSTRUCTION_MEASUREMENT_COMPETENCE_OUT_OF_CONTRACT"
            await session.rollback()
            moved = await service.projects.update_measurement(company_id=company_id, measurement_id=legacy_id,
                request=ConstructionMeasurementUpdate(subcontract_id=later["id"], competence_date=date.today() + timedelta(days=40)))
            assert moved.subcontract_id == later["id"]
    finally:
        await cleanup(factory, company_id)
        await engine.dispose()


@pytest.mark.asyncio
async def test_contract_dnf_covers_approved_contract_measurements_when_totals_match():
    engine = await create_reachable_engine_or_skip()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    company_id = uuid4()
    try:
        async with factory() as session:
            service, project, supplier, contract = await setup(session, company_id)
            project_id = project.id
            first = await measurement(session, service, company_id, project, supplier, contract, "2", "M1")
            second = await measurement(session, service, company_id, project, supplier, contract, "4", "M2")
            for row, net in ((first, Decimal("10")), (second, Decimal("20"))):
                row.status, row.net_amount = "approved", net
            await session.commit()
            document_id = uuid4()
            client = service.projects.erp_client
            client.check_shared_payable.return_value = {"accounts_payable_document_id": str(document_id),
                "accounts_payable_status": "OPEN", "person_id": str(supplier), "total_amount": "30.00"}

            with pytest.raises(ConstructionDomainError) as mismatch:
                await service.projects.link_shared_payable(company_id=company_id, project_id=project_id,
                    payable_document_id=document_id, measurement_ids=[first.id], subcontract_id=contract["id"])
            assert mismatch.value.error_code == "CONSTRUCTION_MEASUREMENT_SHARED_TOTAL_MISMATCH"
            with pytest.raises(ConstructionDomainError) as zero_mode:
                await service.projects.link_shared_payable(company_id=company_id, project_id=project_id,
                    payable_document_id=document_id, measurement_ids=[first.id, second.id])
            assert zero_mode.value.error_code == "CONSTRUCTION_MEASUREMENT_SHARED_NOT_ZERO"

            linked = await service.projects.link_shared_payable(company_id=company_id, project_id=project_id,
                payable_document_id=document_id, measurement_ids=[first.id, second.id], subcontract_id=contract["id"])
            assert linked == 2
            assert first.external_accounts_payable_id == document_id and first.external_accounts_payable_shared
    finally:
        await cleanup(factory, company_id)
        await engine.dispose()


@pytest.mark.asyncio
async def test_global_contract_groups_zero_value_orders_and_limits_dnfs_to_its_total():
    engine = await create_reachable_engine_or_skip()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    company_id = uuid4()
    try:
        async with factory() as session:
            service, project, supplier, _ = await setup(session, company_id)
            project_id = project.id
            created = await service.save(company_id, project_id, SubcontractRequest(code="CT-G", title="Empreitada global",
                supplier_person_id=supplier, valid_from=date.today(), valid_to=date.today() + timedelta(days=60),
                pricing_mode="GLOBAL", global_amount="100.00", items=[]), uuid4())
            contract = await service.release(company_id, created["id"], uuid4())
            assert contract["pricing_mode"] == "GLOBAL" and contract["remaining_amount"] == "100.00"
            orders = []
            for code in ("OS-1", "OS-2"):
                row = ConstructionMeasurement(id=uuid4(), company_id=company_id, project_id=project_id, code=code,
                    measured_amount=Decimal("0"), gross_amount=Decimal("0"), net_amount=Decimal("0"),
                    retentions_amount=Decimal("0"), due_date=date.today(), supplier_person_id=supplier,
                    status="approved", retention_details=[])
                session.add(row)
                orders.append(row)
            valued = ConstructionMeasurement(id=uuid4(), company_id=company_id, project_id=project_id, code="OS-3",
                measured_amount=Decimal("10"), gross_amount=Decimal("10"), net_amount=Decimal("10"),
                retentions_amount=Decimal("0"), due_date=date.today(), supplier_person_id=supplier,
                status="approved", retention_details=[])
            session.add(valued)
            await session.commit()
            order_ids, valued_id = [row.id for row in orders], valued.id

            with pytest.raises(ConstructionDomainError, match="tem valor próprio"):
                await service.link_orders(company_id, contract["id"], [valued_id], uuid4())
            await session.rollback()
            assert await service.link_orders(company_id, contract["id"], order_ids, uuid4()) == 2

            first_dnf, second_dnf = uuid4(), uuid4()
            client = service.projects.erp_client
            client.check_shared_payable.return_value = {"accounts_payable_document_id": str(first_dnf),
                "accounts_payable_status": "OPEN", "person_id": str(supplier), "total_amount": "60.00"}
            await service.projects.link_shared_payable(company_id=company_id, project_id=project_id,
                payable_document_id=first_dnf, measurement_ids=[order_ids[0]], subcontract_id=contract["id"])
            listed = {row["id"]: row for row in await service.list(company_id, project_id)}
            assert listed[contract["id"]]["paid_amount"] == "60.00" and listed[contract["id"]]["remaining_amount"] == "40.00"

            client.check_shared_payable.return_value = {"accounts_payable_document_id": str(second_dnf),
                "accounts_payable_status": "OPEN", "person_id": str(supplier), "total_amount": "50.00"}
            with pytest.raises(ConstructionDomainError, match="passa do saldo"):
                await service.projects.link_shared_payable(company_id=company_id, project_id=project_id,
                    payable_document_id=second_dnf, measurement_ids=[order_ids[1]], subcontract_id=contract["id"])
            await session.rollback()

            with pytest.raises(ConstructionDomainError, match="Remova a OS"):
                await service.unlink_orders(company_id, contract["id"], [order_ids[0]], uuid4())
            await session.rollback()
            client.check_shared_payable.return_value = {"accounts_payable_document_id": str(first_dnf),
                "accounts_payable_status": "OPEN", "person_id": str(supplier), "total_amount": "60.00"}
            await service.projects.unlink_shared_payable(company_id=company_id, project_id=project_id,
                payable_document_id=first_dnf, measurement_ids=[order_ids[0]])
            listed = {row["id"]: row for row in await service.list(company_id, project_id)}
            assert listed[contract["id"]]["remaining_amount"] == "100.00"
            payable = await session.scalar(select(ConstructionSubcontractPayable).where(
                ConstructionSubcontractPayable.company_id == company_id))
            assert payable.status == "REMOVED"
    finally:
        await cleanup(factory, company_id)
        await engine.dispose()


@pytest.mark.asyncio
async def test_items_follow_the_project_service_list_and_keep_service_once_measured():
    engine = await create_reachable_engine_or_skip()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    company_id = uuid4()
    try:
        async with factory() as session:
            service, project, supplier, contract = await setup(session, company_id)
            masonry = ConstructionServiceTemplate(id=uuid4(), company_id=company_id, name="Alvenaria")
            painting = ConstructionServiceTemplate(id=uuid4(), company_id=company_id, name="Pintura")
            session.add_all([masonry, painting])
            await session.flush()
            session.add(ConstructionProjectServiceTemplate(id=uuid4(), company_id=company_id,
                project_id=project.id, service_template_id=masonry.id))
            await session.commit()
            original = contract["items"][0]

            def request(**item):
                return SubcontractRequest(code="CT-1", title="Alvenaria", supplier_person_id=supplier,
                    valid_from=contract["valid_from"], valid_to=contract["valid_to"],
                    items=[{"id": original["id"], "description": "Parede", "unit_of_measure": "M2",
                        "quantity": "10", "material_unit_price": "2", "labor_unit_price": "3", **item}])

            with pytest.raises(ConstructionDomainError, match="lista de serviços"):
                await service.save(company_id, project.id, request(), uuid4(), contract_id=contract["id"])
            with pytest.raises(ConstructionDomainError, match="Pintura não está na lista"):
                await service.save(company_id, project.id, request(service_template_id=painting.id), uuid4(),
                    contract_id=contract["id"])
            saved = await service.save(company_id, project.id, request(service_template_id=masonry.id), uuid4(),
                contract_id=contract["id"])
            assert saved["items"][0]["service_template_id"] == masonry.id
            assert saved["items"][0]["service_template_name"] == "Alvenaria"
            released = await service.release(company_id, contract["id"], uuid4())
            listed = await service.list(company_id, project.id)
            assert listed[0]["total_amount"] == "50.00"

            await measurement(session, service, company_id, project, supplier, released, "2", "M1")
            await session.execute(ConstructionSubcontractItem.__table__.update()
                .where(ConstructionSubcontractItem.id == original["id"]).values(consumed_quantity=Decimal("2")))
            await session.commit()
            await session.execute(delete(ConstructionProjectServiceTemplate).where(
                ConstructionProjectServiceTemplate.company_id == company_id))
            await session.commit()
            with pytest.raises(ConstructionDomainError, match="Serviço e unidade"):
                await service.save(company_id, project.id, request(service_template_id=painting.id), uuid4(),
                    contract_id=contract["id"])
    finally:
        await cleanup(factory, company_id)
        await engine.dispose()
