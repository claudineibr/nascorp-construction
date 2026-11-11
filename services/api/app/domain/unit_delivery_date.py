from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

from app.domain.business_clock import current_business_timezone


def delivery_calendar_date(value):
    if value is None:
        return None
    return value.astimezone(ZoneInfo(current_business_timezone())).date()


def delivery_timestamp(value):
    return datetime.combine(value, time.min, ZoneInfo(current_business_timezone())).astimezone(UTC)
