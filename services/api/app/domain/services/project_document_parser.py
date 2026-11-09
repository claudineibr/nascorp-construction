import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import BytesIO
from zipfile import ZipFile

from openpyxl import load_workbook
from pypdf import PdfReader

from app.domain.exceptions import ConstructionInvalidValueError


MAX_DOCUMENT_BYTES = 8 * 1024 * 1024
CONTRACT_NUMBER = re.compile(r"\b(\d{1,12})\s*/\s*(\d{4})\b")
CONTRACT_LABEL = re.compile(r"\bcontrato\s+(?:administrativo|de servi[cç]os)\s*(?:n[º°o.]*)?\s*", re.I)
CNPJ = re.compile(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}")
ITEM_NUMBER = re.compile(r"\d+(?:\.\d+)+")


def normalized_label(value):
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode()
    return " ".join(text.casefold().split())


def contract_number(text):
    label = CONTRACT_LABEL.search(text)
    match = CONTRACT_NUMBER.match(text, label.end()) if label else None
    if not match:
        raise ConstructionInvalidValueError(message="Não foi possível identificar o número do contrato.")
    return f"{int(match[1])}/{match[2]}"


def parse_contract(content):
    reader = PdfReader(BytesIO(content))
    if reader.is_encrypted or len(reader.pages) > 250:
        raise ConstructionInvalidValueError(message="Envie um PDF pesquisável, sem senha e com até 250 páginas.")
    pages = [" ".join(page.extract_text().split()) for page in reader.pages[:8]]
    text = " ".join(pages)
    number = contract_number(text)
    object_match = re.search(r"\b1\.1[.\s]+(.+?)(?=\s+1\.2[.\s])", text)
    term_match = re.search(r"\b2\.1[.\s]+(.+?)(?=\s+2\.2[.\s])", text)
    value_match = re.search(r"\b5\.1[.\s]+.{0,130}?R\$\s*([\d.]+,\d{2})", text)
    party_match = re.search(r"\b(?:O|A)\s+((?:Munic[ií]pio|Prefeitura Municipal)\s+de\s+[^,;]+)", pages[0], re.I)
    cnpj_match = CNPJ.search(pages[0])
    if not object_match or not cnpj_match:
        raise ConstructionInvalidValueError(message="O PDF precisa identificar o objeto e o CNPJ do contratante.")
    object_text = object_match[1]
    term_text = term_match[1] if term_match else None
    city_match = re.search(r"munic[ií]pio de\s+([^,]+)", object_text, re.I)
    return {
        "contract_number": number,
        "customer": party_match[1].strip() if party_match else None,
        "customer_document": re.sub(r"\D", "", cnpj_match[0]),
        "name": f"Obra em {city_match[1]}" if city_match else f"Obra do contrato {number}",
        "object": object_text[:2000],
        "object_page": next((i for i, page in enumerate(pages, 1) if object_text[:50] in page), 1),
        "term": term_text,
        "term_page": next((i for i, page in enumerate(pages, 1) if term_text and term_text[:50] in page), None),
        "contract_value": value_match[1] if value_match else None,
    }


def decimal_cell(sheet, cell):
    value = sheet[cell].value
    if value is None or isinstance(value, bool):
        raise ConstructionInvalidValueError(message=f"Confira o valor da célula {cell} e salve a planilha recalculada.")
    number = Decimal(str(value))
    if not number.is_finite() or abs(number) > Decimal("1000000000000"):
        raise InvalidOperation
    return number


def money(number):
    return str(number.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def parse_measurement(content):
    with ZipFile(BytesIO(content)) as archive:
        entries = archive.infolist()
        if len(entries) > 500 or sum(entry.file_size for entry in entries) > 64 * 1024 * 1024:
            raise ConstructionInvalidValueError(message="A planilha excede o limite de conteúdo para importação.")
    workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
    try:
        source = next((sheet for sheet in workbook if normalized_label(sheet.title) == "boletim de medicao"), None)
        if source is None or not source.max_row or not source.max_column or source.max_row > 1500 or source.max_column > 150:
            raise ConstructionInvalidValueError(message="Use uma planilha no formato Boletim de Medição.")
        rows = list(source.values)
        header = next((index for index, row in enumerate(rows) if normalized_label(row[0]) == "item"
                       and normalized_label(row[2]) == "descricao"), None)
        summary = next((index for index, row in enumerate(rows) if normalized_label(row[0]) == "% do contrato executado"), None)
        if header is None or summary is None or header >= summary or len(rows[header]) < 12:
            raise ConstructionInvalidValueError(message="O boletim precisa conter os serviços e o resumo da medição.")
        sheet = {cell.coordinate: cell for row in source.iter_rows() for cell in row if cell.value is not None}
        number = contract_number(str(rows[4][4]))
        customer_document = CNPJ.search(str(rows[5][2]))
        measured_on = rows[2][8]
        sequence = re.match(r"\s*(\d{1,8})", str(rows[3][8]))
        if not isinstance(measured_on, date) or not sequence or int(sequence[1]) < 1 or not customer_document:
            raise ConstructionInvalidValueError(message="Confira o CNPJ do contratante, a data e o número no cabeçalho do boletim.")
        if isinstance(measured_on, datetime):
            measured_on = measured_on.date()
        phases = []
        for index in range(header + 1, summary):
            row = rows[index]
            item = str(row[0] or "").strip()
            if not row[2]:
                continue
            line = index + 1
            if item.isdecimal() and row[3] is None:
                phases.append({
                    "name": str(row[2]).strip()[:255], "row": line, "items": [],
                    "contracted": money(decimal_cell(sheet, f"G{line}")),
                    "measured": money(decimal_cell(sheet, f"I{line}")),
                    "accumulated": money(decimal_cell(sheet, f"K{line}")),
                })
            elif ITEM_NUMBER.fullmatch(item) and phases:
                phases[-1]["items"].append({
                    "code": item, "name": str(row[2]).strip()[:1000], "row": line, "unit": str(row[3] or ""),
                    "quantity": str(row[7]) if row[7] is not None else "0",
                    "measured": money(decimal_cell(sheet, f"I{line}")),
                    "accumulated": money(decimal_cell(sheet, f"K{line}")),
                })
        if not phases or len({normalized_label(phase["name"]) for phase in phases}) != len(phases):
            raise ConstructionInvalidValueError(message="O boletim precisa identificar cada etapa com um nome distinto.")
        actual = decimal_cell(sheet, f"G{summary + 1}")
        planned = decimal_cell(sheet, f"I{summary + 1}")
        if not 0 <= actual <= 1 or not 0 <= planned <= 1:
            raise ConstructionInvalidValueError(message="Os percentuais do resumo precisam estar entre 0% e 100%.")
        return {
            "contract_number": number,
            "customer_document": re.sub(r"\D", "", customer_document[0]),
            "measured_on": measured_on.isoformat(),
            "sequence": int(sequence[1]),
            "sheet": source.title,
            "summary_row": summary + 1,
            "actual_percent": money(actual * 100),
            "planned_percent": money(planned * 100),
            "variance_points": money((actual - planned) * 100),
            "measured": money(decimal_cell(sheet, f"G{summary}")),
            "phases": phases,
        }
    finally:
        workbook.close()


def parse_project_document(kind, content):
    if not content or len(content) > MAX_DOCUMENT_BYTES:
        raise ConstructionInvalidValueError(message="Selecione um arquivo não vazio de até 8 MB.")
    try:
        return parse_contract(content) if kind == "contract" else parse_measurement(content)
    except ConstructionInvalidValueError:
        raise
    except Exception as exc:
        raise ConstructionInvalidValueError(
            message="Não foi possível ler o documento. Confira o formato e salve uma nova cópia."
        ) from exc
