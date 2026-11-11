from app.domain.constants import ConstructionProjectStatus


def project_schedule_status(project, *, today):
    if project.status == ConstructionProjectStatus.CANCELLED:
        return "cancelled"
    if project.status == ConstructionProjectStatus.PAUSED:
        return "paused"
    history = getattr(project, "completion_history", None) or []
    reopened_on = history[-1].get("reopened_on") if history else None
    current_end_date = project.actual_end_date
    if current_end_date is not None and reopened_on and current_end_date.isoformat() <= reopened_on:
        current_end_date = None
    if project.status == ConstructionProjectStatus.COMPLETED or (
        current_end_date is not None and current_end_date <= today
    ):
        return "completed"
    if project.expected_end_date is not None and project.expected_end_date < today:
        return "delayed"
    if project.start_date is None or project.start_date > today:
        if project.planned_start_date is not None and project.planned_start_date < today:
            return "delayed"
        return "not_started"
    if project.expected_end_date is None:
        return "no_deadline"
    return "on_time"
