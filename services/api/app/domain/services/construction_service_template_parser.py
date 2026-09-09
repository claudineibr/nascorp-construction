from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO

from openpyxl import load_workbook

from app.domain.exceptions import ConstructionInvalidValueError

SERVICE_NAME_ROW_INDEX = 0
SERVICE_NAME_PRIMARY_COLUMN_INDEX = 2
SERVICE_NAME_FALLBACK_COLUMN_INDEX = 3
ITEMS_FIRST_ROW_INDEX = 4
ITEM_DESCRIPTION_COLUMN_INDEX = 0
ITEM_VERIFICATION_METHOD_COLUMN_INDEX = 2
SERVICE_NAME_KEYWORD = "servico"


@dataclass
class ParsedServiceTemplateItem:
    sequence_number: int
    description: str
    verification_method: str


@dataclass
class ParsedServiceTemplate:
    name: str
    items: list[ParsedServiceTemplateItem] = field(default_factory=list)


def _normalize(value: object) -> str:
    if value is None:
        return ""

    return " ".join(str(value).split()).strip()


def _fold_accents(value: str) -> str:
    replacements = {
        "á": "a", "à": "a", "ã": "a", "â": "a", "ä": "a",
        "é": "e", "ê": "e", "è": "e",
        "í": "i", "ì": "i",
        "ó": "o", "õ": "o", "ô": "o", "ò": "o",
        "ú": "u", "ù": "u", "ü": "u",
        "ç": "c",
    }
    folded = value.lower()
    for accented, plain in replacements.items():
        folded = folded.replace(accented, plain)

    return folded


def _read_service_name(rows: list[list[object]]) -> str:
    if not rows:
        raise ConstructionInvalidValueError(
            message="Spreadsheet is empty.",
            error_code="CONSTRUCTION_TEMPLATE_EMPTY_SPREADSHEET",
        )

    header_row = rows[SERVICE_NAME_ROW_INDEX]
    raw_name = _normalize(_cell(header_row, SERVICE_NAME_PRIMARY_COLUMN_INDEX))
    if not raw_name:
        raw_name = _normalize(_cell(header_row, SERVICE_NAME_FALLBACK_COLUMN_INDEX))

    if SERVICE_NAME_KEYWORD not in _fold_accents(raw_name):
        raise ConstructionInvalidValueError(
            message="Service name not found in the spreadsheet header.",
            error_code="CONSTRUCTION_TEMPLATE_SERVICE_NOT_FOUND",
        )

    if ":" in raw_name:
        raw_name = raw_name.split(":", 1)[1].strip()

    if not raw_name:
        raise ConstructionInvalidValueError(
            message="Service name not found in the spreadsheet header.",
            error_code="CONSTRUCTION_TEMPLATE_SERVICE_NOT_FOUND",
        )

    return raw_name.upper()


def _cell(row: list[object], column_index: int) -> object:
    if column_index >= len(row):
        return None

    return row[column_index]


def parse_service_template_spreadsheet(*, file_name: str, content: bytes) -> ParsedServiceTemplate:
    if not file_name.lower().endswith((".xlsx", ".xlsm")):
        raise ConstructionInvalidValueError(
            message="Only .xlsx spreadsheets are supported. Convert the file before importing.",
            error_code="CONSTRUCTION_TEMPLATE_UNSUPPORTED_FORMAT",
        )

    try:
        workbook = load_workbook(BytesIO(content), data_only=True, read_only=True)
    except Exception as exc:
        raise ConstructionInvalidValueError(
            message="Spreadsheet could not be read.",
            error_code="CONSTRUCTION_TEMPLATE_UNREADABLE_SPREADSHEET",
        ) from exc

    try:
        worksheet = workbook.worksheets[0]
        rows = [list(row) for row in worksheet.iter_rows(values_only=True)]
    finally:
        workbook.close()

    template = ParsedServiceTemplate(name=_read_service_name(rows=rows))

    seen_descriptions: set[str] = set()
    for row in rows[ITEMS_FIRST_ROW_INDEX:]:
        description = _normalize(_cell(row, ITEM_DESCRIPTION_COLUMN_INDEX)).upper()
        verification_method = _normalize(_cell(row, ITEM_VERIFICATION_METHOD_COLUMN_INDEX)).upper()
        if not description or not verification_method:
            break

        if description in seen_descriptions:
            continue

        seen_descriptions.add(description)
        template.items.append(
            ParsedServiceTemplateItem(
                sequence_number=len(template.items) + 1,
                description=description,
                verification_method=verification_method,
            )
        )

    if not template.items:
        raise ConstructionInvalidValueError(
            message="No inspection items found in the spreadsheet.",
            error_code="CONSTRUCTION_TEMPLATE_WITHOUT_ITEMS",
        )

    return template
