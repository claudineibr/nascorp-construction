"""Quais obras o ator enxerga -- a segunda dimensão da autorização.

A primeira dimensão é `feature x ação` e já existe em `ConstructionContext.can`.
Esta é a outra pergunta: *dentro* de Obras, quais obras. Quem decide não é este
serviço -- é o ERP, dono da tabela `record_access_grants`, que manda o resultado
pronto em `GET /v1/internal/construction/permissions`.

Três regras que o resto do código depende e que são fáceis de desfazer:

1. **`unrestricted` não é "todas as obras".** É a sentinela que manda o
   repositório PULAR o filtro. Materializar a lista para o MASTER montaria um
   `IN` com a empresa inteira.
2. **Conjunto vazio nega, e nega de verdade.** `frozenset()` é falsy em Python;
   quem escrever `if scope.project_ids:` trata "não pode nada" como "pode tudo".
   Pergunte sempre `scope.unrestricted` primeiro.
3. **Ausência do campo no payload é irrestrito, de propósito.** ERP anterior ao
   plano 23 não manda `record_access_unrestricted`, e fail-closed ali trancaria
   Obras inteira para todo mundo numa subida fora de ordem. O padrão seguro aqui
   é o oposto do padrão seguro dentro do ERP: lá a ausência é um bug de
   resolução; aqui é uma versão antiga, em que a restrição simplesmente não
   existe.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ProjectScope:
    unrestricted: bool
    project_ids: frozenset[UUID]

    @classmethod
    def unlimited(cls) -> "ProjectScope":
        return cls(unrestricted=True, project_ids=frozenset())

    @classmethod
    def limited_to(cls, project_ids) -> "ProjectScope":
        return cls(unrestricted=False, project_ids=frozenset(project_ids))

    @classmethod
    def nothing(cls) -> "ProjectScope":
        return cls(unrestricted=False, project_ids=frozenset())

    def allows(self, project_id: UUID | None) -> bool:
        if self.unrestricted:
            return True
        if project_id is None:
            return False
        return project_id in self.project_ids
