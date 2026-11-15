from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.domain.events.constants import ErpEventType
from app.domain.services.construction_project_service import ConstructionProjectService


@pytest.mark.parametrize("development_type,current,expected", [
    ("CONTRACT_WORK", None, 10), ("INCORPORATION", None, None),
    (None, None, None), ("CONTRACT_WORK", 15, 15),
])
def test_cost_center_confirmation_inherits_default_only_for_contract_work(development_type, current, expected):
    project = SimpleNamespace(id=uuid4(), company_id=uuid4(), development_type=development_type,
        nfse_receivable_due_days=current, synthetic_cost_center_id=None, analytic_cost_center_id=None)
    event = SimpleNamespace(event_type=ErpEventType.COST_CENTER_CREATED, payload={
        "construction_project_id": str(project.id), "synthetic_cost_center_id": str(uuid4()),
        "analytic_cost_center_id": str(uuid4()), "nfse_receivable_due_days": 10,
    })
    ConstructionProjectService._apply_cost_center_snapshot_from_event(project=project, event=event)
    assert project.nfse_receivable_due_days == expected


def test_project_created_event_carries_the_actual_development_type():
    project = SimpleNamespace(id=uuid4(), company_id=uuid4(), code="EMP-TEST", name="Empreitada",
        project_type="PUBLIC", development_type="CONTRACT_WORK", customer_person_id=None,
        start_date=None, expected_end_date=None, cnpj_spe=None, address_json=None)
    event = ConstructionProjectService._build_project_created_event(project=project, actor_user_id=None)
    assert event.payload["development_type"] == "CONTRACT_WORK"
