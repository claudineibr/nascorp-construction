"""Tirar o dono da unidade com parcela no ERP -- recusado.

Levantado pelo cliente em 2026-09-22. Quem responde pela divida e o COMPRADOR:
`receivables.person_id` sai de `construction_units.buyer_person_id`, tanto na
venda viva quanto na carga do MFCON. Zerar o comprador aqui nao apagava nada no
ERP -- o recebivel seguia inteiro, no nome de quem era dono, e a unidade so
deixava de alcanca-lo pela tela. A divida ficava orfa por RELACAO, que e a pior
forma: nao aparece em relatorio nenhum.

Duas portas tiravam o dono. `release_unit_reservation` zera `buyer_person_id`
direto; `delete_unit` levava a unidade inteira -- e o dono junto -- sem guard
nenhum.
"""

from uuid import uuid4

import httpx
import pytest

from app.domain.constants import ConstructionUnitStatus
from app.domain.exceptions import ConstructionResourceInUseError
from app.domain.services import ConstructionProjectService
from app.infrastructure.database.models import ConstructionUnit
from app.schemas.construction import ConstructionUnitReserveRequest


class _RepositorioFalso:
    def __init__(self, unit):
        self.unit = unit
        self.apagados = []
        self.commits = 0

    async def get_unit(self, *, company_id, unit_id):
        if self.unit is None or self.unit.id != unit_id:
            return None
        return self.unit

    async def delete(self, entity):
        self.apagados.append(entity)

    async def commit(self):
        self.commits += 1

    async def refresh(self, _entity):
        return None


class _ErpFalso:
    """So o metodo que o guard usa. `chamadas` guarda o que foi perguntado."""

    def __init__(self, *, parcelas=0, falha=False):
        self.parcelas = parcelas
        self.falha = falha
        self.chamadas = []

    async def get_unit_payment_plan(self, **kwargs):
        self.chamadas.append(kwargs)
        if self.falha:
            raise httpx.ConnectError("erp fora do ar")
        return {"installments": [{"installment_number": n + 1} for n in range(self.parcelas)]}


def _unidade(*, comprador=None, status=ConstructionUnitStatus.RESERVED):
    return ConstructionUnit(
        id=uuid4(),
        company_id=uuid4(),
        project_id=uuid4(),
        code="MOR-001316",
        unit_type="Moradia",
        status=status,
        buyer_person_id=comprador or uuid4(),
    )


def _servico(unit, erp):
    return ConstructionProjectService(repository=_RepositorioFalso(unit), erp_client=erp)


@pytest.mark.asyncio
async def test_liberar_reserva_com_parcela_e_recusado():
    unit = _unidade()
    comprador = unit.buyer_person_id
    erp = _ErpFalso(parcelas=61)
    service = _servico(unit, erp)

    with pytest.raises(ConstructionResourceInUseError) as erro:
        await service.release_unit_reservation(company_id=unit.company_id, unit_id=unit.id)

    assert erro.value.error_code == "CONSTRUCTION_UNIT_HAS_INSTALLMENTS"
    assert "61" in erro.value.message
    assert "MOR-001316" in erro.value.message
    # O que importa depois da recusa: o dono continua la.
    assert unit.buyer_person_id == comprador
    assert unit.status == ConstructionUnitStatus.RESERVED


@pytest.mark.asyncio
async def test_liberar_reserva_sem_parcela_continua_funcionando():
    unit = _unidade()
    service = _servico(unit, _ErpFalso(parcelas=0))

    liberada = await service.release_unit_reservation(company_id=unit.company_id, unit_id=unit.id)

    assert liberada.buyer_person_id is None
    assert liberada.status == ConstructionUnitStatus.AVAILABLE


@pytest.mark.asyncio
async def test_excluir_unidade_com_parcela_e_recusado():
    """A porta maior: apagar a unidade tira o dono junto."""
    unit = _unidade(status=ConstructionUnitStatus.SOLD)
    erp = _ErpFalso(parcelas=12)
    repositorio = _RepositorioFalso(unit)
    service = ConstructionProjectService(repository=repositorio, erp_client=erp)

    with pytest.raises(ConstructionResourceInUseError) as erro:
        await service.delete_unit(company_id=unit.company_id, unit_id=unit.id)

    assert erro.value.error_code == "CONSTRUCTION_UNIT_HAS_INSTALLMENTS"
    assert repositorio.apagados == []
    assert repositorio.commits == 0


@pytest.mark.asyncio
async def test_excluir_unidade_sem_parcela_continua_funcionando():
    unit = _unidade(status=ConstructionUnitStatus.AVAILABLE)
    repositorio = _RepositorioFalso(unit)
    service = ConstructionProjectService(repository=repositorio, erp_client=_ErpFalso(parcelas=0))

    await service.delete_unit(company_id=unit.company_id, unit_id=unit.id)

    assert repositorio.apagados == [unit]


@pytest.mark.asyncio
async def test_erp_sem_resposta_recusa_em_vez_de_liberar():
    """Deixar passar sem saber e o proprio defeito que o guard fecha."""
    unit = _unidade()
    comprador = unit.buyer_person_id
    service = _servico(unit, _ErpFalso(falha=True))

    with pytest.raises(ConstructionResourceInUseError) as erro:
        await service.release_unit_reservation(company_id=unit.company_id, unit_id=unit.id)

    assert erro.value.error_code == "CONSTRUCTION_UNIT_INSTALLMENTS_UNKNOWN"
    assert unit.buyer_person_id == comprador


@pytest.mark.asyncio
async def test_a_pergunta_vai_pela_unidade_nao_so_pelo_ponteiro():
    """O aditivo e recebivel PROPRIO, sem ponteiro na unidade.

    E a venda migrada do MFCON so ganhou `external_receivable_id` em
    2026-09-21. Perguntar so pelo ponteiro deixaria 676 unidades passarem pelo
    guard como se nao tivessem parcela nenhuma.
    """
    unit = _unidade()
    unit.external_receivable_id = None
    unit.external_contract_id = None
    erp = _ErpFalso(parcelas=3)
    service = _servico(unit, erp)

    with pytest.raises(ConstructionResourceInUseError):
        await service.release_unit_reservation(company_id=unit.company_id, unit_id=unit.id)

    assert erp.chamadas[0]["construction_unit_id"] == unit.id


@pytest.mark.asyncio
async def test_sem_erp_configurado_o_guard_nao_trava_a_operacao():
    unit = _unidade()
    service = ConstructionProjectService(repository=_RepositorioFalso(unit), erp_client=None)

    liberada = await service.release_unit_reservation(company_id=unit.company_id, unit_id=unit.id)

    assert liberada.buyer_person_id is None


@pytest.mark.asyncio
async def test_reservar_continua_gravando_o_comprador():
    """O guard e so na saida do dono -- a entrada nao muda."""
    unit = _unidade(status=ConstructionUnitStatus.AVAILABLE)
    unit.buyer_person_id = None
    erp = _ErpFalso(parcelas=99)
    service = _servico(unit, erp)
    comprador = uuid4()

    reservada = await service.reserve_unit(
        company_id=unit.company_id,
        unit_id=unit.id,
        request=ConstructionUnitReserveRequest(buyer_person_id=comprador),
    )

    assert reservada.buyer_person_id == comprador
    assert erp.chamadas == []
