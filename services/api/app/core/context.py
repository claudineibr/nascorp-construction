from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ConstructionContext:
    company_id: UUID
    user_id: UUID
    person_id: UUID | None
    feature_permissions: dict[str, int]

    def can(self, feature: str, action: int) -> bool:
        return (int(self.feature_permissions.get(feature, 0)) & action) == action
