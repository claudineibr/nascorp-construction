from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE = "America/Sao_Paulo"
BRAZIL_TIMEZONES = {
    "America/Noronha": "Fernando de Noronha",
    "America/Belem": "Belém",
    "America/Fortaleza": "Fortaleza",
    "America/Recife": "Recife",
    "America/Araguaina": "Araguaína",
    "America/Maceio": "Maceió",
    "America/Bahia": "Bahia",
    "America/Sao_Paulo": "Brasília / São Paulo",
    "America/Campo_Grande": "Campo Grande",
    "America/Cuiaba": "Cuiabá",
    "America/Santarem": "Santarém",
    "America/Porto_Velho": "Porto Velho",
    "America/Boa_Vista": "Boa Vista",
    "America/Manaus": "Manaus",
    "America/Eirunepe": "Eirunepé",
    "America/Rio_Branco": "Rio Branco",
}
_clock = ContextVar("business_clock", default=None)


def validate_business_timezone(value):
    if value not in BRAZIL_TIMEZONES:
        raise ValueError("Selecione um fuso horário brasileiro válido")

    ZoneInfo(value)
    return value


def current_business_timezone():
    state = _clock.get()
    return state[0] if state else DEFAULT_TIMEZONE


def bind_business_timezone(value):
    validate_business_timezone(value)
    state = _clock.get()
    _clock.set((value, state[1] if state else datetime.now(timezone.utc)))


def get_business_now(tz, *, instant=None):
    state = _clock.get()
    reference = instant or (state[1] if state else datetime.now(timezone.utc))
    if reference.tzinfo is None:
        raise ValueError("O instante deve conter fuso horário")

    return reference.astimezone(ZoneInfo(tz))


def get_business_today(tz, *, instant=None):
    return get_business_now(tz, instant=instant).date()


def business_date_range(start, end, tz):
    zone = ZoneInfo(tz)
    return (
        datetime.combine(start, time.min, zone).astimezone(timezone.utc),
        datetime.combine(end + timedelta(days=1), time.min, zone).astimezone(timezone.utc),
    )


@contextmanager
def business_clock_scope(tz, *, instant=None):
    validate_business_timezone(tz)
    token = _clock.set((tz, instant or datetime.now(timezone.utc)))
    try:
        yield
    finally:
        _clock.reset(token)


class BusinessClockMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        with business_clock_scope(DEFAULT_TIMEZONE):
            await self.app(scope, receive, send)
