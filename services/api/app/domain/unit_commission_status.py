from app.domain.constants import ConstructionUnitCommissionStatus


def unit_commission_status(*, due_date, payment_date, today):
    if payment_date is not None:
        return ConstructionUnitCommissionStatus.PAID
    if due_date < today:
        return ConstructionUnitCommissionStatus.OVERDUE
    return ConstructionUnitCommissionStatus.OPEN
