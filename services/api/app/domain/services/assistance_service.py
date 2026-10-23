import json
import logging
from datetime import UTC, datetime
from uuid import uuid4

from app.domain.business_clock import current_business_timezone, get_business_today
from app.domain.exceptions import ConstructionDomainError, ConstructionNotFoundError
from app.infrastructure.database.models.assistance import (
    AssistanceRequest,
    AssistanceContact,
    AssistanceComplaint,
    AssistanceService,
    AssistanceHistory,
)


logger = logging.getLogger(__name__)


def active(rows):
    return [row for row in rows if row.deleted_at is None]


def stored_person_ids(row):
    if row is None:
        return set()
    stored = set()
    for item in [row, *active(row.complaints), *active(row.services)]:
        stored.update(getattr(item, column.name) for column in item.__table__.columns if column.name.endswith("person_id"))
    return stored - {None}


def pending_stage(row):
    if row.status == "completed":
        return "completed"
    complaints = active(row.complaints)
    services = active(row.services)
    if not complaints or any(
        c.provenance == "pending" or not c.analyzed_by_person_id or not c.analyzed_at for c in complaints
    ):
        return "analysis"
    if any(c.provenance == "valid" and not any(s.complaint_id == c.id for s in services) for c in complaints):
        return "planning"
    if any(not s.due_date or not s.executed_at or not s.executed_by_person_id for s in services):
        return "execution"
    if any(not s.inspected_at or not s.inspected_by_person_id for s in services):
        return "inspection"
    return "completion"


def serialize_summary(row, labels=None):
    fields = (
        "id",
        "company_id",
        "project_id",
        "unit_id",
        "customer_person_id",
        "attendant_person_id",
        "analyst_person_id",
        "number",
        "status",
        "opened_at",
        "completed_at",
    )
    result = {key: getattr(row, key) for key in fields}
    today = get_business_today(current_business_timezone())
    result["overdue"] = any(s.due_date and s.due_date < today and not s.executed_at for s in active(row.services))
    result["pending_stage"] = pending_stage(row)
    if labels:
        projects, units, people = labels
        result.update(
            project_name=projects.get(row.project_id),
            unit_code=units.get(row.unit_id),
            customer_name=people.get(row.customer_person_id),
            attendant_name=people.get(row.attendant_person_id),
        )
    return result


def serialize(row, labels=None):
    result = {column.name: getattr(row, column.name) for column in row.__table__.columns if column.name != "deleted_at"}
    for key in ("contacts", "complaints", "services", "history"):
        rows = getattr(row, key)
        if key != "history":
            rows = active(rows)
        result[key] = [
            {column.name: getattr(child, column.name) for column in child.__table__.columns if column.name != "deleted_at"}
            for child in rows
        ]
    result.update(serialize_summary(row, labels))
    return result


class AssistanceRequestService:
    def __init__(self, repository):
        self.repository = repository

    def invalid(self, message):
        logger.info(f"[sat] validacao_recusada: motivo={message}")
        raise ConstructionDomainError(message=message, status_code=422)

    async def get(self, company_id, request_id, lock=False):
        row = await self.repository.get(company_id, request_id, lock)
        if row is None:
            raise ConstructionNotFoundError(resource_name="a SAT")
        return row

    async def print_context(self, company_id, request_id):
        row = await self.get(company_id, request_id)
        logger.info(f"[sat] imprimir: company_id={company_id} sat_id={request_id}")
        return {
            "sat": serialize(row, await self.repository.labels([row])),
            "people": await self.repository.print_people(row),
            **await self.repository.print_location(company_id, row.project_id),
            **await self.repository.print_branding(company_id),
        }

    async def validate(self, company_id, data, row=None):
        project = await self.repository.project(company_id, data.project_id, lock=row is None)
        if project is None or await self.repository.unit(company_id, data.project_id, data.unit_id) is None:
            self.invalid("Obra ou unidade indisponível para esta empresa e seu acesso.")
        if row and (row.project_id != data.project_id or row.unit_id != data.unit_id):
            self.invalid("A obra e a unidade da SAT não podem ser alteradas.")
        if not data.attendant_person_id:
            self.invalid("O usuário logado precisa ter uma pessoa vinculada para registrar o atendimento.")
        ids = {data.customer_person_id, data.attendant_person_id}
        ids.update([data.analyst_person_id] if data.analyst_person_id else [])
        for child in [*data.complaints, *data.services]:
            ids.update(value for key, value in child.model_dump().items() if key.endswith("person_id") and value)
        new_ids = ids - stored_person_ids(row)
        if await self.repository.valid_people(company_id, new_ids) != new_ids:
            logger.info(f"[assistance] save: person outside company refused, company_id={company_id}")
            self.invalid("Há pessoas sem vínculo ativo com esta empresa, inexistentes ou excluídas no atendimento.")
        if data.opened_at > datetime.now(UTC):
            self.invalid("A abertura não pode estar no futuro.")
        existing_complaints = {c.id: c for c in active(row.complaints)} if row else {}
        complaint_ids = {c.id for c in data.complaints if c.id}
        if len(complaint_ids) != sum(c.id is not None for c in data.complaints):
            self.invalid("Reclamação repetida no atendimento.")
        for complaint in data.complaints:
            if complaint.id and complaint.id not in existing_complaints:
                self.invalid("Reclamação não pertence à SAT.")
            old = existing_complaints.get(complaint.id)
            self.validate_description(complaint, old)
            unchanged = old and all(
                getattr(old, key) == value for key, value in complaint.model_dump(exclude={"id"}).items()
            )
            if unchanged and data.opened_at == row.opened_at:
                continue
            if not old and complaint.provenance != "pending":
                self.invalid("Reclamações novas começam com procedência Pendente.")
            if bool(complaint.analyzed_at) != bool(complaint.analyzed_by_person_id):
                self.invalid("Informe analista e data da análise juntos.")
            if complaint.analyzed_at and (
                complaint.provenance == "pending"
                or complaint.analyzed_at < data.opened_at
                or complaint.analyzed_at > datetime.now(UTC)
            ):
                self.invalid("Confira a procedência e a data da análise, após a abertura e sem data futura.")
        for service in data.services:
            if service.complaint_id and service.complaint_id not in complaint_ids:
                self.invalid("O serviço deve apontar para uma reclamação ativa desta SAT.")
            old = next((s for s in active(row.services) if s.id == service.id), None) if row else None
            self.validate_description(service, old)
            complaint = next((c for c in data.complaints if service.complaint_id and c.id == service.complaint_id), None)
            analyses = [complaint] if complaint else []
            analysis_unchanged = all(
                c.id in existing_complaints
                and all(
                    getattr(existing_complaints[c.id], key) == getattr(c, key)
                    for key in ("provenance", "analyzed_at", "analyzed_by_person_id")
                )
                for c in analyses
            )
            if (
                old
                and analysis_unchanged
                and data.opened_at == row.opened_at
                and all(getattr(old, key) == value for key, value in service.model_dump(exclude={"id"}).items())
            ):
                continue
            for prefix in ("executed", "inspected"):
                when = getattr(service, f"{prefix}_at")
                who = getattr(service, f"{prefix}_by_person_id")
                if bool(when) != bool(who):
                    self.invalid("Informe responsável e data juntos na execução e na inspeção.")
                if when and (when < data.opened_at or when > datetime.now(UTC)):
                    self.invalid("Execução e inspeção devem ocorrer após a abertura e sem data futura.")
            if service.inspected_at and (not service.executed_at or service.inspected_at < service.executed_at):
                self.invalid("A inspeção deve ocorrer após a execução.")
            if service.executed_at and any(
                not c.analyzed_at
                or not c.analyzed_by_person_id
                or c.provenance == "pending"
                or service.executed_at < c.analyzed_at
                for c in analyses
            ):
                self.invalid("Registre a análise da reclamação vinculada antes da execução.")

    def validate_description(self, data, old):
        if not data.description.strip() and not (
            old is not None and old.source_id is not None and old.description == data.description
        ):
            self.invalid(
                "Informe a descrição da reclamação ou do serviço. Somente descrições vazias originais do histórico podem ser preservadas."
            )

    def event(self, row, actor, action, payload):
        self.repository.add(AssistanceHistory(request_id=row.id, actor_user_id=actor, action=action, payload=payload))
        logger.info(f"[sat] {action}: sat_id={row.id} company_id={row.company_id} actor={actor}")

    def sync(self, row, key, inputs, model):
        existing = {child.id: child for child in active(getattr(row, key))}
        seen = set()
        for data in inputs:
            if data.id and (data.id not in existing or data.id in seen):
                self.invalid("Item inexistente, repetido ou de outra SAT.")
            child = existing.get(data.id)
            if child is None:
                child = model(id=uuid4(), request_id=row.id)
                getattr(row, key).append(child)
            seen.add(child.id)
            for name, value in data.model_dump(exclude={"id"}).items():
                setattr(child, name, value)
        for child_id, child in existing.items():
            if child_id not in seen:
                child.deleted_at = datetime.now(UTC)

    async def save(self, company_id, data, actor, request_id=None, *, actor_person_id=None):
        logger.info(f"[sat] salvar: company_id={company_id} sat_id={request_id}")
        await self.repository.release_operation(company_id)
        row = await self.get(company_id, request_id, True) if request_id else None
        if row and row.status != "open":
            self.invalid("Reabra a SAT antes de alterar o atendimento.")
        data = data.model_copy(update={
            "attendant_person_id": row.attendant_person_id if row else actor_person_id,
        })
        logger.info(
            f"[sat] responsavel_atendimento: company_id={company_id} sat_id={request_id} "
            f"actor_user_id={actor} attendant_person_id={data.attendant_person_id}"
        )
        await self.validate(company_id, data, row)
        before = serialize(row) if row else None
        if before:
            before.pop("history", None)
        if row is None:
            row = AssistanceRequest(
                id=uuid4(),
                company_id=company_id,
                number=await self.repository.next_number(company_id, data.project_id),
                status="open",
                contacts=[],
                complaints=[],
                services=[],
                history=[],
            )
            self.repository.add(row)
        for key, value in data.model_dump(exclude={"contacts", "complaints", "services"}).items():
            setattr(row, key, value)
        for key, model in (
            ("contacts", AssistanceContact),
            ("complaints", AssistanceComplaint),
            ("services", AssistanceService),
        ):
            self.sync(row, key, getattr(data, key), model)
        await self.repository.flush()
        await self.repository.refresh(row, ["created_at", "updated_at"])
        after = serialize(row)
        after.pop("history", None)
        self.event(
            row,
            actor,
            "updated" if request_id else "created",
            json.loads(json.dumps({"before": before, "after": after}, default=str)),
        )
        await self.repository.commit()
        return await self.get(company_id, row.id)

    async def transition(self, company_id, request_id, actor, action, justification=None):
        await self.repository.release_operation(company_id)
        row = await self.get(company_id, request_id, True)
        previous = {"status": row.status, "completed_at": str(row.completed_at) if row.completed_at else None}
        if action == "completed":
            if row.status != "open" or pending_stage(row) != "completion":
                self.invalid(
                    "Conclusão exige análise de todas as reclamações, serviços vinculados às procedentes e prazo, execução e inspeção de cada serviço."
                )
            row.status = "completed"
            row.completed_at = datetime.now(UTC)
        elif action == "reopened":
            if row.status != "completed" or not justification or len(justification.strip()) < 10:
                self.invalid("Reabertura exige SAT concluída e justificativa com pelo menos 10 caracteres.")
            row.status = "open"
            row.completed_at = None
        elif action == "deleted":
            row.deleted_at = datetime.now(UTC)
        self.event(row, actor, action, {**previous, "justification": justification})
        await self.repository.commit()
        return row if action == "deleted" else await self.get(company_id, row.id)
