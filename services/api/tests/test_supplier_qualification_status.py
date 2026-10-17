"""O status de qualificacao do fornecedor no momento em que o registro nasce.

Fase 04A do plano de migracao do MFCON. Duas garantias, e as duas foram medidas
no legado antes de virarem codigo:

1. O Obras **avisa, nao bloqueia** -- 69 fornecedores fecharam 359 pedidos de
   compra sem nenhuma qualificacao. Barrar de saida trancaria a operacao no dia
   do corte.
2. O status e resolvido **no servidor**, e degrada para `none` quando o ERP nao
   responde. E material de auditoria da Caixa: quem grava o registro tem de ser
   quem consultou, e uma indisponibilidade do core nao pode virar bloqueio pela
   porta dos fundos.
"""

from decimal import Decimal
from pydantic import ValidationError
from uuid import uuid4

import httpx
import pytest

from app.domain.constants import ConstructionProjectStatus
from app.domain.services import ConstructionProjectService
from app.infrastructure.database.models import ConstructionProject
from app.schemas.construction import ConstructionProcurementRequestCreate

from app.infrastructure.clients.erp_construction import ErpConstructionClient
from app.domain.exceptions import ConstructionPersonOutsideCompanyError

from .test_construction_project_service import FakeConstructionRepository, FakeErpPeopleDirectory


class FakeQualificationClient(FakeErpPeopleDirectory):
    """So o pedaco do contrato que importa aqui."""

    def __init__(self, *, status: str | None = None, fails: bool = False) -> None:
        self.status = status
        self.fails = fails
        self.calls: list[dict] = []

    async def get_person_qualification_status(self, *, company_id, user_id, person_id) -> str:
        self.calls.append(
            {"company_id": company_id, "user_id": user_id, "person_id": person_id}
        )
        if self.fails:
            return "none"
        return self.status or "none"

    async def validate_procurement_products(self, *, company_id, user_id, product_ids):
        return [
            {"id": str(product_id), "code": "CIM-001", "description": "Cimento CP-II", "default_unit_of_measure": "SC"}
            for product_id in product_ids
        ]


def _project(company_id):
    return ConstructionProject(
        id=uuid4(),
        company_id=company_id,
        code="OBRA-QUAL",
        name="Residencial Jardim",
        status=ConstructionProjectStatus.DRAFT,
    )


async def _create_request(service, *, company_id, project_id, supplier_person_id, actor_user_id=None):
    return await service.create_procurement_request(
        company_id=company_id,
        project_id=project_id,
        request=ConstructionProcurementRequestCreate(
            code="RC-001",
            title="Cimento CP-II",
            items=[{"product_id": uuid4(), "quantity": Decimal("10"), "unit_of_measure": "SC", "unit_price": Decimal("150.00")}],
            supplier_person_id=supplier_person_id,
        ),
        actor_user_id=actor_user_id,
    )


@pytest.mark.asyncio
async def test_requisicao_guarda_o_status_que_valia_na_criacao() -> None:
    company_id = uuid4()
    supplier_person_id = uuid4()
    actor_user_id = uuid4()
    repository = FakeConstructionRepository()
    project = _project(company_id)
    repository.projects[(company_id, project.id)] = project
    client = FakeQualificationClient(status="expired")
    service = ConstructionProjectService(repository=repository, erp_client=client)

    created = await _create_request(
        service,
        company_id=company_id,
        project_id=project.id,
        supplier_person_id=supplier_person_id,
        actor_user_id=actor_user_id,
    )

    assert created.supplier_qualification_status == "expired"
    assert client.calls[0]["person_id"] == supplier_person_id
    assert client.calls[0]["user_id"] == actor_user_id


@pytest.mark.asyncio
async def test_fornecedor_sem_qualificacao_nao_impede_a_requisicao() -> None:
    """359 pedidos do legado sao exatamente deste caso."""
    company_id = uuid4()
    repository = FakeConstructionRepository()
    project = _project(company_id)
    repository.projects[(company_id, project.id)] = project
    service = ConstructionProjectService(
        repository=repository,
        erp_client=FakeQualificationClient(status="none"),
    )

    created = await _create_request(
        service,
        company_id=company_id,
        project_id=project.id,
        supplier_person_id=uuid4(),
    )

    assert created.id is not None
    assert created.supplier_qualification_status == "none"


@pytest.mark.asyncio
async def test_fornecedor_reprovado_tambem_e_salvo_com_o_status_registrado() -> None:
    company_id = uuid4()
    repository = FakeConstructionRepository()
    project = _project(company_id)
    repository.projects[(company_id, project.id)] = project
    service = ConstructionProjectService(
        repository=repository,
        erp_client=FakeQualificationClient(status="rejected"),
    )

    created = await _create_request(
        service,
        company_id=company_id,
        project_id=project.id,
        supplier_person_id=uuid4(),
    )

    assert created.supplier_qualification_status == "rejected"


@pytest.mark.asyncio
async def test_sem_fornecedor_rejeita_antes_de_consultar_o_erp() -> None:
    company_id = uuid4()
    repository = FakeConstructionRepository()
    project = _project(company_id)
    repository.projects[(company_id, project.id)] = project
    client = FakeQualificationClient(status="approved")
    service = ConstructionProjectService(repository=repository, erp_client=client)

    with pytest.raises(ValidationError):
        await _create_request(
            service,
            company_id=company_id,
            project_id=project.id,
            supplier_person_id=None,
        )
    assert client.calls == []


@pytest.mark.asyncio
async def test_falha_na_consulta_de_qualificacao_nao_impede_a_requisicao() -> None:
    """A qualificacao e informativa; a validacao do produto continua obrigatoria."""
    company_id = uuid4()
    repository = FakeConstructionRepository()
    project = _project(company_id)
    repository.projects[(company_id, project.id)] = project
    service = ConstructionProjectService(repository=repository, erp_client=FakeQualificationClient(fails=True))

    created = await _create_request(
        service,
        company_id=company_id,
        project_id=project.id,
        supplier_person_id=uuid4(),
    )

    assert created.supplier_qualification_status == "none"
    assert len(service.erp_client.calls) == 1


@pytest.mark.asyncio
async def test_cliente_degrada_para_none_quando_o_erp_falha(monkeypatch) -> None:
    """ERP fora do ar nao pode virar bloqueio: o campo e aviso, nao gate."""
    client = ErpConstructionClient()

    async def _explode(**_kwargs):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(client, "list_person_summaries", _explode)

    status = await client.get_person_qualification_status(
        company_id=uuid4(), user_id=uuid4(), person_id=uuid4()
    )

    assert status == "none"


@pytest.mark.asyncio
async def test_cliente_degrada_para_none_quando_o_core_nao_devolve_o_campo(monkeypatch) -> None:
    """Deploy do ERP primeiro, Obras depois: a ausencia do campo e esperada."""
    client = ErpConstructionClient()
    person_id = uuid4()

    async def _sem_o_campo(**_kwargs):
        return {"items": [{"id": str(person_id), "name": "Fornecedor"}], "total": 1}

    monkeypatch.setattr(client, "list_person_summaries", _sem_o_campo)

    status = await client.get_person_qualification_status(
        company_id=uuid4(), user_id=uuid4(), person_id=person_id
    )

    assert status == "none"


@pytest.mark.asyncio
async def test_cliente_recusa_fornecedor_sem_vinculo_com_a_empresa(monkeypatch) -> None:
    client = ErpConstructionClient()

    async def _sem_a_pessoa(**_kwargs):
        return {"items": [], "total": 0}

    monkeypatch.setattr(client, "list_person_summaries", _sem_a_pessoa)

    with pytest.raises(ConstructionPersonOutsideCompanyError):
        await client.get_person_qualification_status(company_id=uuid4(), user_id=uuid4(), person_id=uuid4())


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code,degrades", [(404, False), (503, True)])
async def test_cliente_distingue_pessoa_inexistente_de_erp_indisponivel(monkeypatch, status_code, degrades) -> None:
    client = ErpConstructionClient()
    request = httpx.Request("GET", "http://erp/v1/internal/construction/person-summaries")

    async def _falha(**_kwargs):
        raise httpx.HTTPStatusError("erp", request=request, response=httpx.Response(status_code, request=request))

    monkeypatch.setattr(client, "list_person_summaries", _falha)

    if degrades:
        assert await client.get_person_qualification_status(
            company_id=uuid4(), user_id=uuid4(), person_id=uuid4()
        ) == "none"
    else:
        with pytest.raises(ConstructionPersonOutsideCompanyError):
            await client.get_person_qualification_status(company_id=uuid4(), user_id=uuid4(), person_id=uuid4())


@pytest.mark.asyncio
async def test_requisicao_com_fornecedor_de_outra_empresa_e_recusada() -> None:
    company_id = uuid4()
    supplier_person_id = uuid4()
    repository = FakeConstructionRepository()
    project = _project(company_id)
    repository.projects[(company_id, project.id)] = project
    client = FakeQualificationClient(status="approved")
    client.foreign_person_ids = {supplier_person_id}
    service = ConstructionProjectService(repository=repository, erp_client=client)

    with pytest.raises(ConstructionPersonOutsideCompanyError, match="O fornecedor"):
        await _create_request(
            service, company_id=company_id, project_id=project.id, supplier_person_id=supplier_person_id
        )
    assert client.calls == []
    assert repository.procurement_requests == {}


@pytest.mark.asyncio
async def test_cliente_devolve_o_status_que_o_core_mandou(monkeypatch) -> None:
    client = ErpConstructionClient()
    person_id = uuid4()
    recebido = {}

    async def _com_status(**kwargs):
        recebido.update(kwargs)
        return {
            "items": [{"id": str(person_id), "qualification_status": "approved"}],
            "total": 1,
        }

    monkeypatch.setattr(client, "list_person_summaries", _com_status)

    status = await client.get_person_qualification_status(
        company_id=uuid4(), user_id=uuid4(), person_id=person_id
    )

    assert status == "approved"
    # Filtra pela pessoa em vez de baixar a listagem inteira.
    assert recebido["person_id"] == person_id
