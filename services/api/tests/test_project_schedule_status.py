from datetime import date
from types import SimpleNamespace

import pytest

from app.domain.project_schedule_status import project_schedule_status


@pytest.mark.parametrize(("end_date", "history", "status", "expected"), [
    (date(2026, 9, 30), [{"completed_on": "2026-09-30", "reopened_on": "2026-10-01"}], "active", "on_time"),
    (date(2026, 10, 1), [{"completed_on": "2026-10-01", "reopened_on": "2026-10-01"}], "active", "on_time"),
    (date(2026, 11, 10), [{"completed_on": "2026-09-30", "reopened_on": "2026-10-01"}], "active", "completed"),
    (date(2026, 9, 30), None, "active", "completed"),
    (None, None, "completed", "completed"),
])
def test_current_situation_respects_completion_history(end_date, history, status, expected):
    project = SimpleNamespace(
        status=status, actual_end_date=end_date, completion_history=history,
        start_date=date(2026, 1, 1), planned_start_date=date(2026, 1, 1),
        expected_end_date=date(2026, 12, 31),
    )
    assert project_schedule_status(project, today=date(2026, 11, 11)) == expected
