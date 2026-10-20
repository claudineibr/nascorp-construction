from datetime import datetime
from zoneinfo import ZoneInfo

BRAZIL_TIMEZONE = ZoneInfo("America/Sao_Paulo")


def brazil_today():
    return datetime.now(BRAZIL_TIMEZONE).date()
