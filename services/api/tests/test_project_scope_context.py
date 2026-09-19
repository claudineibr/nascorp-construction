"""O escopo por obra atravessando a fronteira ERP -> Obras.

Obras **não consegue** decidir quem vê o quê: a tabela de concessões é do ERP, e
este contrato descarta `role_ids` -- MASTER não é dedutível daqui. Por isso o
ERP manda a resposta pronta, e o risco fica sendo o transporte dela.

Três coisas que quebram em silêncio, cada uma com um teste:

1. **O campo some no meio do caminho** e todo mundo vira irrestrito.
2. **A ausência do campo tranca a empresa inteira** -- o oposto, e é por isso que
   o padrão aqui é irrestrito e não fail-closed: ERP anterior ao plano 23 não
   manda nada, e nessa versão a restrição simplesmente não existe.
3. **A fábrica do serviço resolve o contexto de novo** e cada requisição passa a
   bater duas vezes no ERP -- 79 rotas pagando o dobro de latência.
"""

from uuid import UUID, uuid4

from fastapi import Depends
from fastapi.testclient import TestClient

from app.core import security as security_module
from app.core.context import ConstructionContext
from app.core.security import get_permission_client, require_permission
from app.domain.permissions import ConstructionFeature, PermissionAction
from app.infrastructure.clients import EffectivePermissions
from app.infrastructure.clients import erp_permissions as modulo_permissoes
from app.infrastructure.clients.erp_permissions import ErpPermissionClient
from app.infrastructure.database.session import get_session
from app.main import create_app
from app.presentation.routes.construction_projects import get_project_service
from tests.test_construction_project_routes import TEST_SECRET, make_authorization_header


class _RespostaFalsa:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self.payload


class _ClienteHttpFalso:
    payload: dict = {}

    def __init__(self, *, base_url, timeout):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args) -> None:
        return None

    async def get(self, endpoint, *, headers):
        return _RespostaFalsa(_ClienteHttpFalso.payload)


async def _buscar(payload, monkeypatch):
    _ClienteHttpFalso.payload = payload
    monkeypatch.setattr(modulo_permissoes.httpx, "AsyncClient", _ClienteHttpFalso)
    monkeypatch.setattr(modulo_permissoes.settings, "erp_service_key", "chave-de-teste")
    return await ErpPermissionClient().get_effective_permissions(
        company_id=UUID(payload["company_id"]),
        user_id=UUID(payload["user_id"]),
    )


def _payload_base(**extra):
    base = {
        "company_id": str(uuid4()),
        "user_id": str(uuid4()),
        "person_id": str(uuid4()),
        "feature_permissions": {ConstructionFeature.PROJECTS: PermissionAction.READ},
    }
    base.update(extra)
    return base


async def test_o_escopo_do_erp_chega_inteiro(monkeypatch) -> None:
    permitida = uuid4()
    payload = _payload_base(record_access_unrestricted=False, allowed_project_ids=[str(permitida)])

    efetivas = await _buscar(payload, monkeypatch)

    assert efetivas.record_access_unrestricted is False
    assert efetivas.allowed_project_ids == frozenset({permitida})


async def test_lista_vazia_com_restricao_ligada_nega_de_verdade(monkeypatch) -> None:
    """`frozenset()` é falsy. Quem testar a verdade da lista em vez do booleano
    transforma "não pode nada" em "pode tudo"."""
    payload = _payload_base(record_access_unrestricted=False, allowed_project_ids=[])

    efetivas = await _buscar(payload, monkeypatch)

    assert efetivas.record_access_unrestricted is False
    assert efetivas.allowed_project_ids == frozenset()


async def test_campo_ausente_e_irrestrito_e_nao_tranca_a_empresa(monkeypatch) -> None:
    """ERP anterior ao plano 23 não manda o campo. Fail-closed aqui tiraria
    Obras do ar inteira numa subida fora de ordem, e o que falta não é uma
    concessão: é a feature."""
    efetivas = await _buscar(_payload_base(), monkeypatch)

    assert efetivas.record_access_unrestricted is True
    assert efetivas.allowed_project_ids == frozenset()


# --------------------------------------------- do contrato ate o repositorio


class _ClientePermissaoFalso:
    def __init__(self, *, permissoes, unrestricted, obras):
        self.permissoes = permissoes
        self.unrestricted = unrestricted
        self.obras = obras
        self.chamadas = 0

    async def get_effective_permissions(self, *, company_id, user_id):
        self.chamadas += 1
        return EffectivePermissions(
            company_id=company_id,
            user_id=user_id,
            person_id=uuid4(),
            feature_permissions=self.permissoes,
            record_access_unrestricted=self.unrestricted,
            allowed_project_ids=frozenset(self.obras),
        )


def _app_de_teste(cliente):
    """Um app real com uma rota de teste: a cadeia de dependencias e a mesma.

    `get_session` entra falso porque o que esta sob teste e a costura do
    contexto ate o repositorio -- nenhuma consulta e emitida.
    """
    security_module.settings.jwt_secret_key = TEST_SECRET
    app = create_app()
    app.dependency_overrides[get_permission_client] = lambda: cliente
    app.dependency_overrides[get_session] = lambda: object()

    @app.get("/teste/escopo")
    async def _rota(
        ctx: ConstructionContext = Depends(
            require_permission(ConstructionFeature.PROJECTS, PermissionAction.READ)
        ),
        servico=Depends(get_project_service),
    ):
        escopo = servico.repository.scope
        return {
            "do_contexto": sorted(str(valor) for valor in ctx.project_scope.project_ids),
            "do_repositorio": sorted(str(valor) for valor in escopo.project_ids),
            "irrestrito": escopo.unrestricted,
        }

    return app


def _chamar(app):
    with TestClient(app) as client:
        return client.get(
            "/teste/escopo",
            headers={
                "Authorization": make_authorization_header(user_id=uuid4()),
                "X-Company-ID": str(uuid4()),
            },
        )


def test_o_escopo_do_erp_chega_ate_o_repositorio() -> None:
    """A costura inteira: o que o ERP respondeu e o que o repositorio filtra.

    E a unica ligacao entre as duas metades da fase 3. Quebrada, nada da erro:
    o repositorio simplesmente nasce irrestrito e todo mundo volta a ver tudo.
    """
    permitida = uuid4()
    cliente = _ClientePermissaoFalso(
        permissoes={ConstructionFeature.PROJECTS: PermissionAction.FULL},
        unrestricted=False,
        obras=[permitida],
    )

    resposta = _chamar(_app_de_teste(cliente))

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["irrestrito"] is False
    assert corpo["do_repositorio"] == [str(permitida)]
    assert corpo["do_contexto"] == corpo["do_repositorio"]


def test_a_fabrica_do_servico_nao_consulta_o_erp_de_novo() -> None:
    """`get_project_service` passou a pedir o contexto. Sem o reaproveitamento
    que o FastAPI faz por requisicao, cada chamada bateria DUAS vezes no ERP --
    em 79 rotas, e por HTTP."""
    cliente = _ClientePermissaoFalso(
        permissoes={ConstructionFeature.PROJECTS: PermissionAction.FULL},
        unrestricted=False,
        obras=[uuid4()],
    )

    resposta = _chamar(_app_de_teste(cliente))

    assert resposta.status_code == 200
    assert cliente.chamadas == 1, "o contexto foi resolvido duas vezes na mesma requisicao"


def test_ator_irrestrito_nao_leva_filtro_nenhum_ao_repositorio() -> None:
    """MASTER, e a empresa em modo sombra, nao pagam EXISTS por consulta."""
    cliente = _ClientePermissaoFalso(
        permissoes={ConstructionFeature.PROJECTS: PermissionAction.FULL},
        unrestricted=True,
        obras=[],
    )

    corpo = _chamar(_app_de_teste(cliente)).json()

    assert corpo["irrestrito"] is True
    assert corpo["do_repositorio"] == []


def test_contexto_sem_escopo_nasce_irrestrito() -> None:
    """Todo chamador anterior monta o contexto sem escopo. O padrao tem de
    manter o comportamento de antes do plano 23, e nao esconder tudo deles."""
    ctx = ConstructionContext(
        company_id=uuid4(),
        user_id=uuid4(),
        person_id=None,
        feature_permissions={},
    )

    assert ctx.project_scope.unrestricted is True
