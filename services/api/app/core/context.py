from dataclasses import dataclass, field
from uuid import UUID

from app.domain.record_scope import ProjectScope


@dataclass(frozen=True)
class ConstructionContext:
    """Quem esta pedindo, e o que ele pode -- nas DUAS dimensoes.

    `feature_permissions` responde 'pode ler medicao?'. `project_scope`
    responde 'de quais obras?'. As duas sao independentes: quem pode tudo
    em Obras ainda pode enxergar tres obras de cinquenta.

    O padrao irrestrito mantem de pe todo teste e todo chamador que monta o
    contexto sem escopo -- e o mesmo padrao que o contrato com o ERP adota.
    """

    company_id: UUID
    user_id: UUID
    person_id: UUID | None
    feature_permissions: dict[str, int]
    project_scope: ProjectScope = field(default_factory=ProjectScope.unlimited)

    def can(self, feature: str, action: int) -> bool:
        return (int(self.feature_permissions.get(feature, 0)) & action) == action
