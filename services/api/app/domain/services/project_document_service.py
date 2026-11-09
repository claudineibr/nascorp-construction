import asyncio
import hashlib
import logging
import re
from uuid import uuid4

from app.domain.business_clock import get_business_today
from app.domain.exceptions import ConstructionInvalidValueError, ConstructionNotFoundError, ConstructionResourceInUseError
from app.domain.services.project_document_parser import normalized_label, parse_project_document
from app.infrastructure.database.models.construction import ConstructionSchedulePhase
from app.infrastructure.database.models.project_document import ConstructionProjectDocument
from app.schemas.construction.project import ConstructionProjectCreate
from app.schemas.construction.project_document import ProjectDocumentHistory, ProjectDocumentResponse


logger = logging.getLogger(__name__)


def preview_document(kind, file_name, content):
    snapshot = parse_project_document(kind, content)
    name = file_name.replace("\\", "/").rsplit("/", 1)[-1]
    return {"kind": kind, "file_name": re.sub(r"[\x00-\x1f\x7f]", "", name)[:255], "snapshot": snapshot}


class ProjectDocumentService:
    def __init__(self, project_service, documents, company_id, actor_user_id, timezone):
        self.projects = project_service
        self.documents = documents
        self.company_id = company_id
        self.actor_user_id = actor_user_id
        self.timezone = timezone

    def _document(self, kind, file_name, content, project_id=None):
        preview = preview_document(kind, file_name, content)
        data = preview["snapshot"]
        number = data["contract_number"]
        if kind == "contract":
            identity = f"contract:{data['customer_document']}:{number}"
        else:
            identity = f"measurement:{project_id}:{number}:{data['sequence']}"
        return ConstructionProjectDocument(
            id=uuid4(), company_id=self.company_id, project_id=project_id, actor_user_id=self.actor_user_id,
            identity=identity, sha256=hashlib.sha256(content).hexdigest(), content=content, **preview,
        )

    async def _find_duplicate(self, document):
        await self.documents.lock_identity(self.company_id, document.identity)
        existing = await self.documents.find(self.company_id, document.identity)
        if existing:
            logger.info(f"[project_documents] duplicate: company_id={self.company_id} kind={document.kind} actor_id={self.actor_user_id}")
            if existing.project_id == document.project_id and existing.sha256 == document.sha256:
                return existing
            raise ConstructionResourceInUseError(
                message="Este contrato ou número de medição já foi importado. Confira os documentos da obra."
            )
        return None

    async def create_from_contract(self, file_name, content, code, name):
        logger.info(f"[project_documents] create_from_contract: company_id={self.company_id} actor_id={self.actor_user_id}")
        if not 1 <= len(code.strip()) <= 50 or not 1 <= len(name.strip()) <= 255:
            raise ConstructionInvalidValueError(message="Informe o código e o nome da obra.")
        document = await asyncio.to_thread(self._document, "contract", file_name, content)
        await self._find_duplicate(document)
        request = ConstructionProjectCreate(
            code=code.strip(), name=name.strip(), description=document.snapshot["object"],
            development_type="CONTRACT_WORK",
        )
        project = await self.projects.create_project(
            company_id=self.company_id, request=request, actor_user_id=self.actor_user_id, source_document=document,
        )
        logger.info(f"[project_documents] created: company_id={self.company_id} project_id={project.id} document_id={document.id}")
        return project

    async def require_contract_project(self, project_id, *, for_update=False):
        project = await self.projects.repository.get_project(
            company_id=self.company_id, project_id=project_id, for_update=for_update,
        )
        if project is None:
            raise ConstructionNotFoundError(resource_name="a obra")
        if project.development_type != "CONTRACT_WORK":
            raise ConstructionInvalidValueError(message="Os documentos do cronograma são exclusivos de obras de Empreitada.")

    async def attach(self, project_id, kind, file_name, content, create_phases=False):
        logger.info(f"[project_documents] attach: company_id={self.company_id} project_id={project_id} kind={kind} actor_id={self.actor_user_id}")
        document = await asyncio.to_thread(self._document, kind, file_name, content, project_id)
        await self.require_contract_project(project_id, for_update=True)
        existing = await self._find_duplicate(document)
        if existing:
            return existing
        contracts = await self.documents.list(self.company_id, project_id, ["contract"])
        if kind == "contract" and contracts:
            raise ConstructionResourceInUseError(message="Esta obra já tem um contrato vinculado ao cronograma.")
        if kind == "measurement":
            if not contracts or any(
                contracts[0].snapshot[field] != document.snapshot[field]
                for field in ("contract_number", "customer_document")
            ):
                raise ConstructionInvalidValueError(message="Vincule à obra o contrato identificado no boletim antes de importar.")
            if document.snapshot["measured_on"] > get_business_today(self.timezone).isoformat():
                raise ConstructionInvalidValueError(message="A data da medição está no futuro.")
            await self._map_phases(project_id, document.snapshot["phases"], create_phases)
        await self.projects.repository.add(document)
        await self.projects.repository.commit()
        logger.info(f"[project_documents] attached: company_id={self.company_id} project_id={project_id} document_id={document.id} kind={kind}")
        return document

    async def _map_phases(self, project_id, measured_phases, create_phases):
        phases = await self.projects.repository.list_schedule_phases(company_id=self.company_id, project_id=project_id)
        names = {}
        for phase in phases:
            names.setdefault(normalized_label(phase.name), []).append(phase)
        missing = [phase for phase in measured_phases if normalized_label(phase["name"]) not in names]
        if missing and not create_phases:
            raise ConstructionInvalidValueError(message="Crie as etapas indicadas no boletim ou marque Criar etapas faltantes.")
        next_order = max((phase.sequence_order for phase in phases), default=0)
        for data in measured_phases:
            matches = names.get(normalized_label(data["name"]), [])
            if len(matches) > 1:
                raise ConstructionInvalidValueError(message=f"Há mais de uma etapa com o nome {data['name']}. Revise o cronograma.")
            if matches:
                data["phase_id"] = str(matches[0].id)
                continue
            next_order += 1
            phase = ConstructionSchedulePhase(
                id=uuid4(), company_id=self.company_id, project_id=project_id,
                name=data["name"], sequence_order=next_order,
            )
            await self.projects.repository.add(phase)
            data["phase_id"] = str(phase.id)
        logger.info(f"[project_documents] mapped_phases: company_id={self.company_id} project_id={project_id} matched={len(measured_phases) - len(missing)} created={len(missing)}")

    async def history(self, project_id, kinds):
        await self.require_contract_project(project_id)
        documents = await self.documents.list(self.company_id, project_id, kinds)
        return ProjectDocumentHistory(
            items=[document_summary(document) for document in documents],
            total=len(documents), today=get_business_today(self.timezone),
        )

    async def download(self, project_id, document_id, kinds):
        await self.require_contract_project(project_id)
        document = await self.documents.get_file(self.company_id, project_id, document_id, kinds)
        if document is None:
            raise ConstructionNotFoundError(resource_name="o documento")
        return document


def document_summary(document):
    summary = ProjectDocumentResponse.model_validate(document)
    if summary.kind == "measurement":
        summary.snapshot = {
            **summary.snapshot,
            "phases": [{key: value for key, value in phase.items() if key != "items"}
                       for phase in summary.snapshot["phases"]],
        }
    return summary
