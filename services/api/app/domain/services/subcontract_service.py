from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from app.domain.exceptions import ConstructionDomainError, ConstructionNotFoundError
from app.infrastructure.database.models.subcontract import ConstructionSubcontract, ConstructionSubcontractItem, ConstructionSubcontractVersion, ConstructionSubcontractConsumption, ConstructionSubcontractDirectBill, ConstructionSubcontractDeduction
from app.infrastructure.repository.subcontract_repository import SubcontractRepository


def money(value):
    result = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if not result.is_finite() or abs(result) >= Decimal("1000000000000"):
        raise ConstructionDomainError(message="O valor do contrato excede a precisão financeira permitida.")
    return result


class SubcontractService:
    def __init__(self, projects):
        self.projects = projects
        self.session = projects.repository.session
        self.repository = SubcontractRepository(self.session, projects.repository.scope)

    @staticmethod
    def fail(message):
        raise ConstructionDomainError(message=message, error_code="CONSTRUCTION_SUBCONTRACT_INVALID")

    async def get(self, company_id, contract_id, lock=False):
        row = await self.repository.get(company_id, contract_id, lock)
        if row is None:
            raise ConstructionNotFoundError(resource_name="o contrato de empreitada")
        return row

    @staticmethod
    def header(row):
        return {"id": row.id, "project_id": row.project_id, "code": row.code, "title": row.title,
            "supplier_person_id": row.supplier_person_id, "valid_from": row.valid_from, "valid_to": row.valid_to,
            "status": row.status, "retention_rate": str(row.retention_rate), "escrow_rate": str(row.escrow_rate),
            "escrow_due_date": row.escrow_due_date, "released_version": row.released_version, "notes": row.notes}

    async def detail(self, company_id, contract_id, version_id=None):
        row = await self.get(company_id, contract_id)
        items = await self.repository.items(company_id, contract_id)
        if version_id is not None:
            version = await self.repository.version_by_id(company_id, contract_id, version_id)
            if version is None:
                raise ConstructionNotFoundError(resource_name="a versão do contrato de empreitada")
            consumed = {str(item.id): item.consumed_quantity for item in items}
            return {**version.sheet, "items": [{**item,
                "consumed_quantity": str(consumed.get(item["id"], Decimal("0"))),
                "remaining_quantity": str(max(Decimal("0"), Decimal(item["quantity"]) -
                    consumed.get(item["id"], Decimal("0"))))} for item in version.sheet["items"]]}
        return {**self.header(row), "items": [{"id": item.id, "sequence_number": item.sequence_number,
            "product_id": item.product_id, "description": item.description, "unit_of_measure": item.unit_of_measure,
            "quantity": str(item.quantity), "material_unit_price": str(item.material_unit_price),
            "labor_unit_price": str(item.labor_unit_price), "consumed_quantity": str(item.consumed_quantity),
            "remaining_quantity": str(item.quantity - item.consumed_quantity), "active": item.active}
            for item in sorted(items, key=lambda item: item.sequence_number)],
            "remaining_amount": str(money(sum(((item.quantity - item.consumed_quantity) *
                (item.material_unit_price + item.labor_unit_price) for item in items if item.active), Decimal("0"))))}

    async def save(self, company_id, project_id, request, actor_user_id, contract_id=None):
        await self.projects.get_project(company_id=company_id, project_id=project_id)
        await self.session.commit()
        client = self.projects.erp_client
        if client is None:
            self.fail("Configure a conexão com o ERP para validar o fornecedor do contrato.")
        people = await client.list_person_summaries(company_id=company_id, user_id=actor_user_id,
            search=None, page=1, page_size=1, person_id=request.supplier_person_id, business_role="supplier")
        if not any(str(person.get("id")) == str(request.supplier_person_id) for person in people.get("items", [])):
            self.fail("O fornecedor precisa estar ativo na empresa do contrato.")
        product_ids = list({item.product_id for item in request.items if item.product_id})
        if product_ids:
            products = await client.validate_procurement_products(company_id=company_id, user_id=actor_user_id, product_ids=product_ids)
            if {str(product.get("id")) for product in products} != {str(value) for value in product_ids}:
                self.fail("Os produtos do contrato precisam pertencer à empresa.")
        await self.repository.lock_code(company_id, project_id, request.code.strip())
        duplicate = await self.repository.by_code(company_id, project_id, request.code.strip())
        if duplicate is not None and duplicate.id != contract_id:
            self.fail("Este código de contrato já existe na obra.")
        if contract_id:
            row = await self.get(company_id, contract_id, True)
            if row.project_id != project_id or row.status in {"CLOSED", "CANCELED"}:
                self.fail("O contrato não pode ser alterado nesta obra ou situação.")
        else:
            row = ConstructionSubcontract(id=uuid4(), company_id=company_id, project_id=project_id,
                code=request.code.strip(), title=request.title.strip(), supplier_person_id=request.supplier_person_id,
                valid_from=request.valid_from, valid_to=request.valid_to)
            self.session.add(row)
            await self.session.flush()
        current = await self.repository.items(company_id, row.id, True)
        by_id = {item.id: item for item in current}
        if any(item.id and item.id not in by_id for item in request.items):
            self.fail("Um item informado não pertence a este contrato.")
        if any(item.consumed_quantity > 0 for item in current) and row.supplier_person_id != request.supplier_person_id:
            self.fail("O fornecedor não pode mudar depois de consumir saldo do contrato.")
        supplied_ids = {item.id for item in request.items if item.id}
        for item in current:
            item.active = item.id in supplied_ids
        for sequence, data in enumerate(request.items, 1):
            item = by_id.get(data.id)
            if item is None:
                item = ConstructionSubcontractItem(id=uuid4(), company_id=company_id, contract_id=row.id,
                    sequence_number=max([value.sequence_number for value in current], default=0) + sequence,
                    consumed_quantity=Decimal("0"))
                self.session.add(item)
            if data.quantity < item.consumed_quantity:
                self.fail("A quantidade contratada não pode ficar abaixo do que já foi medido.")
            if item.consumed_quantity and (item.unit_of_measure != data.unit_of_measure or item.product_id != data.product_id):
                self.fail("Produto e unidade de item já medido precisam ser preservados.")
            for field in ("product_id", "description", "unit_of_measure", "quantity", "material_unit_price", "labor_unit_price"):
                setattr(item, field, getattr(data, field))
            if not item.description.strip() or not item.unit_of_measure.strip():
                self.fail("Descrição e unidade do item são obrigatórias.")
            money(item.quantity * (item.material_unit_price + item.labor_unit_price))
            item.active = True
        for field in ("code", "title", "supplier_person_id", "valid_from", "valid_to", "retention_rate", "escrow_rate", "escrow_due_date", "notes"):
            setattr(row, field, getattr(request, field))
        row.code, row.title, row.status = row.code.strip(), row.title.strip(), "DRAFT"
        if not row.code or not row.title:
            self.fail("Código e título do contrato são obrigatórios.")
        await self.session.commit()
        return await self.detail(company_id, row.id)

    async def release(self, company_id, contract_id, actor_user_id):
        row = await self.get(company_id, contract_id, True)
        if row.status != "DRAFT":
            self.fail("Somente uma planilha em preparação pode ser liberada.")
        detail = await self.detail(company_id, contract_id)
        active = [item for item in detail["items"] if item["active"]]
        if not active or sum((Decimal(item["quantity"]) * (Decimal(item["material_unit_price"]) +
            Decimal(item["labor_unit_price"])) for item in active), Decimal("0")) <= 0:
            self.fail("A planilha precisa conter itens ativos com valor positivo.")
        row.released_version += 1
        row.status, row.released_by_user_id = "RELEASED", actor_user_id
        sheet = {**detail, "status": "RELEASED", "released_version": row.released_version,
            "items": [{key: str(value) if key in {"id", "product_id"} and value else value
            for key, value in item.items()} for item in active]}
        sheet = {key: str(value) if key in {"id", "project_id", "supplier_person_id", "valid_from", "valid_to", "escrow_due_date"} and value else value
            for key, value in sheet.items()}
        self.session.add(ConstructionSubcontractVersion(id=uuid4(), company_id=company_id,
            contract_id=row.id, version_number=row.released_version, sheet=sheet, released_by_user_id=actor_user_id))
        await self.session.commit()
        return await self.detail(company_id, contract_id)

    async def bind_item(self, measurement, item, contract_item_id, quantity):
        if not measurement.subcontract_id or quantity is None or quantity <= 0:
            self.fail("Informe contrato, item contratado e quantidade positiva para a medição.")
        contract = await self.get(measurement.company_id, measurement.subcontract_id)
        version = await self.repository.version_by_id(measurement.company_id, contract.id, measurement.subcontract_version_id) if measurement.subcontract_version_id else await self.repository.version(measurement.company_id, contract.id, contract.released_version)
        if contract.status != "RELEASED" or version is None:
            self.fail("Libere a planilha do contrato antes de medir.")
        snapshot = next((row for row in version.sheet["items"] if row["id"] == str(contract_item_id)), None)
        if snapshot is None:
            self.fail("O item não pertence à planilha liberada deste contrato.")
        if measurement.subcontract_version_id and measurement.subcontract_version_id != version.id:
            self.fail("A medição já usa outra versão da planilha; preserve os termos ou inicie uma nova medição.")
        measurement.subcontract_version_id = version.id
        item.subcontract_item_id, item.quantity, item.contract_snapshot = contract_item_id, quantity, snapshot
        item.amount = money(quantity * (Decimal(snapshot["material_unit_price"]) + Decimal(snapshot["labor_unit_price"])))

    async def bind_parent(self, measurement, updates):
        contract_id = updates.get("subcontract_id", measurement.subcontract_id)
        if contract_id != measurement.subcontract_id:
            if await self.repository.measurement_items(measurement.company_id, measurement.id):
                self.fail("Remova os itens ainda não medidos antes de trocar o contrato da medição.")
            measurement.subcontract_version_id = None
        if contract_id is None:
            return
        contract = await self.get(measurement.company_id, contract_id)
        supplier_id = updates.get("supplier_person_id", measurement.supplier_person_id)
        if contract.project_id != measurement.project_id or contract.status != "RELEASED":
            self.fail("Selecione contrato liberado da obra da medição.")
        if supplier_id and supplier_id != contract.supplier_person_id:
            self.fail("O fornecedor da medição precisa corresponder ao contrato.")
        updates["supplier_person_id"] = contract.supplier_person_id

    async def financial_amounts(self, measurement, gross):
        version = await self.repository.version_by_id(measurement.company_id, measurement.subcontract_id, measurement.subcontract_version_id)
        if version is None:
            self.fail("Adicione itens da planilha liberada antes de calcular a medição.")
        deductions = await self.repository.deductions(measurement.company_id, measurement.id)
        measurement.direct_billing_amount = sum((row.amount for row in deductions if row.status != "REVERSED"), Decimal("0"))
        invoice = gross - measurement.direct_billing_amount
        measurement.retentions_amount = money(invoice * Decimal(version.sheet["retention_rate"]) / 100)
        measurement.escrow_amount = money(invoice * Decimal(version.sheet["escrow_rate"]) / 100)
        measurement.escrow_due_date = datetime.fromisoformat(version.sheet["escrow_due_date"]).date() if version.sheet.get("escrow_due_date") else None
        net = invoice - measurement.retentions_amount
        if net <= 0 or measurement.escrow_amount >= invoice:
            self.fail("Retenções, caução e faturamento direto precisam deixar valor líquido positivo.")
        return net

    async def consume(self, measurement):
        if not measurement.subcontract_id:
            return
        contract = await self.get(measurement.company_id, measurement.subcontract_id, True)
        if contract.status != "RELEASED":
            self.fail("O contrato precisa estar liberado para aprovar a medição.")
        if measurement.project_id != contract.project_id or measurement.supplier_person_id != contract.supplier_person_id:
            self.fail("Obra e fornecedor da medição precisam corresponder ao contrato.")
        details = measurement.retention_details or []
        if sum((Decimal(str(tax["tax_amount"])) for tax in details), Decimal("0")) != measurement.retentions_amount:
            self.fail("Identifique os tributos retidos e feche o valor de retenção da medição.")
        if len({tax["tax_type"] for tax in details}) != len(details):
            self.fail("Os tributos da retenção não podem se repetir.")
        if not measurement.document_type or not measurement.document_number:
            self.fail("Informe o tipo e o número do documento fiscal da medição contratual.")
        version = await self.repository.version_by_id(measurement.company_id, contract.id, measurement.subcontract_version_id)
        if version is None:
            self.fail("A versão da planilha não pertence a este contrato.")
        if measurement.competence_date is None or not datetime.fromisoformat(version.sheet["valid_from"]).date() <= measurement.competence_date <= datetime.fromisoformat(version.sheet["valid_to"]).date():
            self.fail("Informe competência dentro da vigência do contrato.")
        active = await self.repository.consumptions(measurement.company_id, measurement.id)
        if active:
            return
        items = await self.repository.items(measurement.company_id, contract.id, True)
        by_id = {item.id: item for item in items}
        lines = await self.repository.measurement_items(measurement.company_id, measurement.id)
        requested = {}
        for line in lines:
            if line.subcontract_item_id not in by_id or not line.quantity or not line.contract_snapshot:
                self.fail("Todos os itens da medição precisam de vínculo e quantidade contratada.")
            requested[line.subcontract_item_id] = requested.get(line.subcontract_item_id, Decimal("0")) + line.quantity
        if not requested:
            self.fail("Adicione itens contratados antes de aprovar a medição.")
        deductions = await self.repository.deductions(measurement.company_id, measurement.id)
        bills = {row.id: row for row in await self.repository.direct_bills(measurement.company_id, contract.id, True)}
        material = sum((money(line.quantity * Decimal(line.contract_snapshot["material_unit_price"])) for line in lines), Decimal("0"))
        if measurement.direct_billing_amount > material:
            self.fail("O desconto de faturamento direto não pode exceder o material previsto nos itens medidos.")
        for deduction in deductions:
            if deduction.status == "REVERSED":
                continue
            bill = bills.get(deduction.direct_bill_id)
            if bill is None or bill.deducted_amount + deduction.amount > bill.amount:
                self.fail("O crédito de faturamento direto mudou ou pertence a outro contrato.")
        for item_id, quantity in requested.items():
            item = by_id[item_id]
            if not item.active or item.consumed_quantity + quantity > item.quantity:
                self.fail(f"Saldo insuficiente para o item {item.description}.")
        measurement.approval_cycle += 1
        for item_id, quantity in requested.items():
            by_id[item_id].consumed_quantity += quantity
        for deduction in deductions:
            if deduction.status == "DRAFT":
                bills[deduction.direct_bill_id].deducted_amount += deduction.amount
                deduction.status, deduction.posted_at = "POSTED", datetime.now(UTC)
        for line in lines:
            snapshot = line.contract_snapshot
            self.session.add(ConstructionSubcontractConsumption(company_id=measurement.company_id,
                contract_item_id=line.subcontract_item_id, version_id=measurement.subcontract_version_id,
                measurement_id=measurement.id, measurement_item_id=line.id, approval_cycle=measurement.approval_cycle,
                quantity=line.quantity, material_amount=money(line.quantity * Decimal(snapshot["material_unit_price"])),
                labor_amount=money(line.quantity * Decimal(snapshot["labor_unit_price"]))))

    async def reverse_consumption(self, measurement, actor_user_id=None):
        if not measurement.subcontract_id:
            return
        await self.get(measurement.company_id, measurement.subcontract_id, True)
        items = {item.id: item for item in await self.repository.items(measurement.company_id, measurement.subcontract_id, True)}
        for row in await self.repository.consumptions(measurement.company_id, measurement.id):
            items[row.contract_item_id].consumed_quantity -= row.quantity
            row.status, row.reversed_by_user_id, row.reversed_at = "REVERSED", actor_user_id, datetime.now(UTC)
        bills = {row.id: row for row in await self.repository.direct_bills(measurement.company_id, measurement.subcontract_id, True)}
        for deduction in await self.repository.deductions(measurement.company_id, measurement.id):
            if deduction.status == "POSTED":
                bills[deduction.direct_bill_id].deducted_amount -= deduction.amount
                deduction.status, deduction.reversed_at = "REVERSED", datetime.now(UTC)

    async def register_direct_bill(self, company_id, contract_id, request, actor_user_id):
        contract = await self.get(company_id, contract_id)
        if contract.status != "RELEASED":
            self.fail("O contrato precisa estar liberado para registrar faturamento direto.")
        project_id = contract.project_id
        await self.session.commit()
        snapshot = await self.projects.erp_client.get_direct_billing_document(company_id=company_id,
            project_id=project_id, document_id=request.payable_document_id, user_id=actor_user_id)
        if Decimal(snapshot["amount"]) < request.amount:
            self.fail("O faturamento direto não pode exceder o documento de material validado no ERP.")
        contract = await self.get(company_id, contract_id, True)
        await self.repository.lock_direct_bill_document(company_id, request.payable_document_id)
        if contract.status != "RELEASED":
            self.fail("O contrato mudou de situação durante a validação do documento.")
        if await self.repository.direct_bill_by_document(company_id, request.payable_document_id):
            self.fail("Este documento já está vinculado a faturamento direto.")
        bill = ConstructionSubcontractDirectBill(id=uuid4(), company_id=company_id, contract_id=contract.id,
            payable_document_id=request.payable_document_id, amount=request.amount, deducted_amount=Decimal("0"),
            verified_by_user_id=actor_user_id, document_snapshot=snapshot)
        self.session.add(bill)
        await self.session.commit()
        return {"id": bill.id, "amount": str(bill.amount), "snapshot": snapshot}

    async def set_deduction(self, company_id, measurement_id, request):
        measurement = await self.repository.measurement(company_id, measurement_id, True)
        if measurement is None or not measurement.subcontract_id or measurement.status not in {"draft", "rejected"}:
            self.fail("Selecione medição contratual ainda editável.")
        await self.get(company_id, measurement.subcontract_id, True)
        bills = {row.id: row for row in await self.repository.direct_bills(company_id, measurement.subcontract_id, True)}
        bill = bills.get(request.direct_bill_id)
        if bill is None or request.amount > bill.amount - bill.deducted_amount:
            self.fail("Crédito de faturamento direto insuficiente ou de outro contrato.")
        rows = await self.repository.deductions(company_id, measurement_id)
        row = next((value for value in rows if value.direct_bill_id == request.direct_bill_id), None)
        if row is None:
            row = ConstructionSubcontractDeduction(company_id=company_id, measurement_id=measurement_id,
                direct_bill_id=bill.id, amount=request.amount, status="DRAFT")
            self.session.add(row)
        else:
            row.amount, row.status = request.amount, "DRAFT"
        await self.session.flush()
        await self.projects._sync_measurement_amounts_from_items(measurement=measurement)
        await self.session.commit()
        return {"id": row.id, "amount": str(row.amount), "status": row.status}

    async def request_reversal(self, company_id, measurement_id, reason, actor_user_id):
        measurement = await self.repository.measurement(company_id, measurement_id, True)
        if measurement is None or not measurement.subcontract_id or measurement.status != "approved":
            self.fail("Somente medição contratual aprovada e sem pagamento pode solicitar estorno.")
        if measurement.reversal_pending:
            event = await self.projects.event_repository.latest_measurement_event(company_id, measurement_id) if self.projects.event_repository else None
            if event is not None and event.payload.get("operation") == "reverse" and event.status == "dead_letter":
                event.payload = {**event.payload, "user_id": str(actor_user_id)}
                event.status, event.retry_count, event.last_error, event.next_attempt_at = "pending", 0, None, None
                await self.session.commit()
            return {"id": measurement.id, "reversal_pending": True}
        if self.projects.event_repository is None:
            self.fail("O estorno exige fila persistente disponível.")
        event = self.projects._build_measurement_approved_event(measurement=measurement,
            analytic_cost_center_id=None, actor_user_id=actor_user_id)
        event.payload["operation"] = "reverse"
        event.payload["reason"] = reason.strip()
        measurement.reversal_pending = True
        await self.projects.event_repository.add_outbox_event(event)
        await self.session.commit()
        return {"id": measurement.id, "reversal_pending": True}

    async def remove_direct_bill(self, company_id, contract_id, bill_id):
        await self.get(company_id, contract_id, True)
        bills = {row.id: row for row in await self.repository.direct_bills(company_id, contract_id, True)}
        bill = bills.get(bill_id)
        if bill is None:
            raise ConstructionNotFoundError(resource_name="o faturamento direto")
        if bill.deducted_amount or await self.repository.bill_has_open_deductions(company_id, bill_id):
            self.fail("Estorne os descontos e remova os vínculos em preparação antes de desvincular o documento.")
        bill.status = "REMOVED"
        await self.session.commit()

    async def remove_deduction(self, company_id, measurement_id, deduction_id):
        measurement = await self.repository.measurement(company_id, measurement_id, True)
        if measurement is None or measurement.status not in {"draft", "rejected"}:
            self.fail("Somente descontos de medição ainda editável podem ser removidos.")
        rows = await self.repository.deductions(company_id, measurement_id)
        row = next((value for value in rows if value.id == deduction_id), None)
        if row is None or row.status == "POSTED":
            self.fail("Desconto não encontrado ou já consumido.")
        row.status = "REVERSED"
        row.reversed_at = datetime.now(UTC)
        await self.projects._sync_measurement_amounts_from_items(measurement=measurement)
        await self.session.commit()

    async def close(self, company_id, contract_id, reason, actor_user_id, cancel=False):
        row = await self.get(company_id, contract_id, True)
        if row.status in {"CLOSED", "CANCELED"}:
            self.fail("Este contrato já está encerrado.")
        items = await self.repository.items(company_id, contract_id, True)
        if cancel and any(item.consumed_quantity > 0 for item in items):
            self.fail("Estorne as medições antes de cancelar o contrato; use encerramento para eliminar apenas o saldo.")
        row.status, row.closure_reason, row.closed_by_user_id = "CANCELED" if cancel else "CLOSED", reason.strip(), actor_user_id
        await self.session.commit()
        return await self.detail(company_id, contract_id)

    async def reopen(self, company_id, contract_id):
        row = await self.get(company_id, contract_id, True)
        if row.status != "CLOSED" or not row.released_version:
            self.fail("Somente contrato encerrado com planilha liberada pode ser reaberto.")
        row.status = "RELEASED"
        await self.session.commit()
        return await self.detail(company_id, contract_id)
