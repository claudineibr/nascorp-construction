from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

from app.domain.exceptions import ConstructionInvalidValueError

SERVICE_NAME_ROW_INDEX = 0
SERVICE_NAME_PRIMARY_COLUMN_INDEX = 2
SERVICE_NAME_FALLBACK_COLUMN_INDEX = 3
ITEMS_FIRST_ROW_INDEX = 4
ITEM_DESCRIPTION_COLUMN_INDEX = 0
ITEM_VERIFICATION_METHOD_COLUMN_INDEX = 2
SERVICE_NAME_KEYWORD = "servico"
DEFAULT_SECTION_NAME = "GERAL"


@dataclass
class ParsedServiceTemplateItem:
    sequence_number: int
    description: str
    verification_method: str


@dataclass
class ParsedServiceTemplateSection:
    sequence_number: int
    name: str
    items: list[ParsedServiceTemplateItem] = field(default_factory=list)


@dataclass
class ParsedServiceTemplate:
    name: str
    sections: list[ParsedServiceTemplateSection] = field(default_factory=list)

    @property
    def items(self) -> list[ParsedServiceTemplateItem]:
        return [item for section in self.sections for item in section.items]


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
            message="A planilha está vazia.",
            error_code="CONSTRUCTION_TEMPLATE_EMPTY_SPREADSHEET",
        )

    header_row = rows[SERVICE_NAME_ROW_INDEX]
    raw_name = _normalize(_cell(header_row, SERVICE_NAME_PRIMARY_COLUMN_INDEX))
    if not raw_name:
        raw_name = _normalize(_cell(header_row, SERVICE_NAME_FALLBACK_COLUMN_INDEX))

    if SERVICE_NAME_KEYWORD not in _fold_accents(raw_name):
        raise ConstructionInvalidValueError(
            message="Não encontramos o nome do serviço no cabeçalho da planilha.",
            error_code="CONSTRUCTION_TEMPLATE_SERVICE_NOT_FOUND",
        )

    if ":" in raw_name:
        raw_name = raw_name.split(":", 1)[1].strip()

    if not raw_name:
        raise ConstructionInvalidValueError(
            message="Não encontramos o nome do serviço no cabeçalho da planilha.",
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
            message="Só aceitamos planilhas .xlsx ou .xlsm. Converta o arquivo antes de importar.",
            error_code="CONSTRUCTION_TEMPLATE_UNSUPPORTED_FORMAT",
        )

    try:
        workbook = load_workbook(BytesIO(content), data_only=True, read_only=True)
    except Exception as exc:
        raise ConstructionInvalidValueError(
            message="Não foi possível ler a planilha.",
            error_code="CONSTRUCTION_TEMPLATE_UNREADABLE_SPREADSHEET",
        ) from exc

    try:
        worksheet = workbook.worksheets[0]
        rows = [list(row) for row in worksheet.iter_rows(values_only=True)]
    finally:
        workbook.close()

    section = ParsedServiceTemplateSection(sequence_number=1, name=DEFAULT_SECTION_NAME)
    template = ParsedServiceTemplate(name=_read_service_name(rows=rows), sections=[section])

    seen_descriptions: set[str] = set()
    for row in rows[ITEMS_FIRST_ROW_INDEX:]:
        description = _normalize(_cell(row, ITEM_DESCRIPTION_COLUMN_INDEX)).upper()
        verification_method = _normalize(_cell(row, ITEM_VERIFICATION_METHOD_COLUMN_INDEX)).upper()
        if not description or not verification_method:
            break

        if description in seen_descriptions:
            continue

        seen_descriptions.add(description)
        section.items.append(
            ParsedServiceTemplateItem(
                sequence_number=len(section.items) + 1,
                description=description,
                verification_method=verification_method,
            )
        )

    if not template.items:
        raise ConstructionInvalidValueError(
            message="Nenhum item de inspeção foi encontrado na planilha.",
            error_code="CONSTRUCTION_TEMPLATE_WITHOUT_ITEMS",
        )

    return template


SAMPLE_SERVICE_NAME = "Aterro / Compactação de aterro"
SAMPLE_ITEMS = (
    ("Terreno limpo, sem vegetação, entulho ou material orgânico.", "Visual"),
    ("Material de aterro disponível, limpo e adequado para aplicação.", "Visual"),
    ("Níveis conferidos conforme projeto, memorial ou levantamento disponível.", "Nível / projeto"),
    ("Lançamento executado em camadas horizontais.", "Visual"),
    ("Espessura das camadas controlada, no máximo 40 cm sem definição em projeto.", "Trena / nível"),
)


def build_service_template_example() -> bytes:
    """Builds the blank spreadsheet offered for download before an import.

    Positions every cell from the same constants the parser reads, so the model
    handed to the user cannot drift away from what the importer accepts. The
    test that parses this very file is what keeps that promise honest.
    """
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "FVS"

    title_font = Font(bold=True, size=12)
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="2563EB")
    wrapped = Alignment(vertical="center", wrap_text=True)

    name_cell = worksheet.cell(
        row=SERVICE_NAME_ROW_INDEX + 1,
        column=SERVICE_NAME_PRIMARY_COLUMN_INDEX + 1,
        value=f"Serviço: {SAMPLE_SERVICE_NAME}",
    )
    name_cell.font = title_font

    worksheet.cell(row=2, column=1, value="FVS - Ficha de Verificação de Serviço")
    worksheet.cell(
        row=3,
        column=1,
        value="Troque o nome depois de 'Serviço:' e substitua os itens abaixo. Um arquivo = um serviço.",
    )

    header_row = ITEMS_FIRST_ROW_INDEX
    description_header = worksheet.cell(
        row=header_row,
        column=ITEM_DESCRIPTION_COLUMN_INDEX + 1,
        value="Item a ser inspecionado",
    )
    method_header = worksheet.cell(
        row=header_row,
        column=ITEM_VERIFICATION_METHOD_COLUMN_INDEX + 1,
        value="Método de Verificação",
    )
    for cell in (description_header, method_header):
        cell.font = header_font
        cell.fill = header_fill

    for offset, (description, method) in enumerate(SAMPLE_ITEMS):
        row = ITEMS_FIRST_ROW_INDEX + 1 + offset
        worksheet.cell(row=row, column=ITEM_DESCRIPTION_COLUMN_INDEX + 1, value=description).alignment = wrapped
        worksheet.cell(row=row, column=ITEM_VERIFICATION_METHOD_COLUMN_INDEX + 1, value=method).alignment = wrapped

    worksheet.column_dimensions["A"].width = 70
    worksheet.column_dimensions["B"].width = 4
    worksheet.column_dimensions["C"].width = 28
    worksheet.column_dimensions["D"].width = 20

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
