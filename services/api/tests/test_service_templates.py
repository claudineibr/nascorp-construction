import io
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from openpyxl import Workbook

from app.domain.constants import ConstructionMeasurementStatus, ConstructionProjectStatus
from app.domain.exceptions import ConstructionInvalidValueError
from app.domain.services import ConstructionProjectService
from app.domain.services.construction_service_template_parser import parse_service_template_spreadsheet
from app.infrastructure.database.models import (
    ConstructionMeasurement,
    ConstructionProject,
    ConstructionUnit,
)
from app.schemas.construction import (
    ConstructionMeasurementItemCreate,
    ConstructionServiceTemplateUpdate,
)
from tests.test_construction_project_service import FakeConstructionRepository


def build_caixa_spreadsheet(*, service_name, items, service_column=3, trailing_noise=True):
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.cell(row=1, column=service_column, value=f"Serviço: {service_name}")
    worksheet.cell(row=2, column=1, value="FICHA DE VERIFICAÇÃO DE SERVIÇO")
    worksheet.cell(row=3, column=1, value="Obra:")
    worksheet.cell(row=4, column=1, value="ITEM")
    worksheet.cell(row=4, column=3, value="MÉTODO DE VERIFICAÇÃO")
    for offset, (description, method) in enumerate(items):
        worksheet.cell(row=5 + offset, column=1, value=description)
        worksheet.cell(row=5 + offset, column=3, value=method)

    if trailing_noise:
        worksheet.cell(row=5 + len(items) + 1, column=1, value="LINHA APOS O BRANCO")

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_parser_reads_service_name_and_inspection_items() -> None:
    content = build_caixa_spreadsheet(
        service_name="Alvenaria de vedação",
        items=[
            ("Locação da alvenaria", "Trena e esquadro"),
            ("Prumo das paredes", "Régua de 2m"),
        ],
    )

    parsed = parse_service_template_spreadsheet(file_name="fvs.xlsx", content=content)

    assert parsed.name == "ALVENARIA DE VEDAÇÃO"
    assert [(item.sequence_number, item.description, item.verification_method) for item in parsed.items] == [
        (1, "LOCAÇÃO DA ALVENARIA", "TRENA E ESQUADRO"),
        (2, "PRUMO DAS PAREDES", "RÉGUA DE 2M"),
    ]


def test_parser_reads_service_name_from_the_fallback_column() -> None:
    content = build_caixa_spreadsheet(
        service_name="Cobertura",
        items=[("Alinhamento das telhas", "Inspeção visual")],
        service_column=4,
    )

    parsed = parse_service_template_spreadsheet(file_name="fvs.xlsx", content=content)

    assert parsed.name == "COBERTURA"


def test_parser_stops_on_the_first_blank_row() -> None:
    content = build_caixa_spreadsheet(
        service_name="Pintura",
        items=[("Demão única", "Visual")],
        trailing_noise=True,
    )

    parsed = parse_service_template_spreadsheet(file_name="fvs.xlsx", content=content)

    assert len(parsed.items) == 1


def test_parser_ignores_duplicated_items() -> None:
    content = build_caixa_spreadsheet(
        service_name="Esquadrias",
        items=[
            ("Vedação do batente", "Visual"),
            ("Vedação do batente", "Outro método"),
            ("Prumo do batente", "Régua"),
        ],
    )

    parsed = parse_service_template_spreadsheet(file_name="fvs.xlsx", content=content)

    assert [item.description for item in parsed.items] == ["VEDAÇÃO DO BATENTE", "PRUMO DO BATENTE"]


def test_parser_rejects_spreadsheet_without_the_service_header() -> None:
    workbook = Workbook()
    workbook.active.cell(row=1, column=3, value="Planilha qualquer")
    buffer = io.BytesIO()
    workbook.save(buffer)

    with pytest.raises(ConstructionInvalidValueError) as error:
        parse_service_template_spreadsheet(file_name="qualquer.xlsx", content=buffer.getvalue())

    assert error.value.error_code == "CONSTRUCTION_TEMPLATE_SERVICE_NOT_FOUND"


def test_parser_rejects_spreadsheet_without_inspection_items() -> None:
    workbook = Workbook()
    workbook.active.cell(row=1, column=3, value="Serviço: Sem itens")
    buffer = io.BytesIO()
    workbook.save(buffer)

    with pytest.raises(ConstructionInvalidValueError) as error:
        parse_service_template_spreadsheet(file_name="vazia.xlsx", content=buffer.getvalue())

    assert error.value.error_code == "CONSTRUCTION_TEMPLATE_WITHOUT_ITEMS"


def test_parser_rejects_legacy_xls_format() -> None:
    with pytest.raises(ConstructionInvalidValueError) as error:
        parse_service_template_spreadsheet(file_name="fvs.xls", content=b"qualquer")

    assert error.value.error_code == "CONSTRUCTION_TEMPLATE_UNSUPPORTED_FORMAT"


def build_service(*, company_id=None):
    return ConstructionProjectService(repository=FakeConstructionRepository()), company_id or uuid4()


@pytest.mark.asyncio
async def test_import_creates_template_with_its_inspection_items() -> None:
    service, company_id = build_service()
    content = build_caixa_spreadsheet(
        service_name="Alvenaria",
        items=[("Locação", "Trena"), ("Prumo", "Régua")],
    )

    results = await service.import_service_templates(
        company_id=company_id,
        files=[("alvenaria.xlsx", content)],
    )

    assert results[0]["status"] == "created"
    assert results[0]["items_count"] == 2

    templates = await service.list_service_templates(company_id=company_id)

    assert len(templates) == 1
    assert templates[0].name == "ALVENARIA"
    assert [item.description for item in templates[0].items] == ["LOCAÇÃO", "PRUMO"]


@pytest.mark.asyncio
async def test_reimporting_the_same_service_is_skipped() -> None:
    service, company_id = build_service()
    content = build_caixa_spreadsheet(service_name="Alvenaria", items=[("Locação", "Trena")])

    await service.import_service_templates(company_id=company_id, files=[("alvenaria.xlsx", content)])
    results = await service.import_service_templates(company_id=company_id, files=[("alvenaria.xlsx", content)])

    assert results[0]["status"] == "skipped"

    templates = await service.list_service_templates(company_id=company_id)

    assert len(templates) == 1
    assert len(templates[0].items) == 1


@pytest.mark.asyncio
async def test_import_reports_failure_per_file_without_losing_the_others() -> None:
    service, company_id = build_service()
    valid_content = build_caixa_spreadsheet(service_name="Cobertura", items=[("Telhas", "Visual")])

    results = await service.import_service_templates(
        company_id=company_id,
        files=[("quebrada.xls", b"nao e xlsx"), ("cobertura.xlsx", valid_content)],
    )

    assert results[0]["status"] == "failed"
    assert results[1]["status"] == "created"
    assert len(await service.list_service_templates(company_id=company_id)) == 1


@pytest.mark.asyncio
async def test_import_without_file_is_refused() -> None:
    service, company_id = build_service()

    with pytest.raises(ConstructionInvalidValueError) as error:
        await service.import_service_templates(company_id=company_id, files=[])

    assert error.value.error_code == "CONSTRUCTION_TEMPLATE_NO_FILE"


async def build_measurement_scenario(*, service, company_id):
    repository = service.repository
    project = ConstructionProject(
        id=uuid4(),
        company_id=company_id,
        code="OBRA-070",
        name="Template project",
        status=ConstructionProjectStatus.ACTIVE,
        analytic_cost_center_id=uuid4(),
    )
    unit = ConstructionUnit(
        id=uuid4(),
        company_id=company_id,
        project_id=project.id,
        code="E-501",
        unit_type="house",
        analytic_cost_center_id=uuid4(),
        status="available",
    )
    measurement = ConstructionMeasurement(
        id=uuid4(),
        company_id=company_id,
        project_id=project.id,
        unit_id=unit.id,
        schedule_phase_id=uuid4(),
        code="MED-070",
        sequence_number=1,
        gross_amount=Decimal("1000.00"),
        retentions_amount=Decimal("0"),
        net_amount=Decimal("1000.00"),
        measured_amount=Decimal("1000.00"),
        due_date=date(2026, 10, 10),
        status=ConstructionMeasurementStatus.DRAFT,
    )
    repository.projects[(company_id, project.id)] = project
    repository.units[(company_id, unit.id)] = unit
    repository.measurements[(company_id, measurement.id)] = measurement
    return measurement


@pytest.mark.asyncio
async def test_measurement_item_from_template_copies_the_inspection_items() -> None:
    service, company_id = build_service()
    content = build_caixa_spreadsheet(
        service_name="Alvenaria",
        items=[("Locação", "Trena"), ("Prumo", "Régua"), ("Encunhamento", "Visual")],
    )
    await service.import_service_templates(company_id=company_id, files=[("alvenaria.xlsx", content)])
    template = (await service.list_service_templates(company_id=company_id))[0]
    measurement = await build_measurement_scenario(service=service, company_id=company_id)

    item = await service.create_measurement_item(
        company_id=company_id,
        measurement_id=measurement.id,
        request=ConstructionMeasurementItemCreate(
            service_template_id=template.id,
            amount=Decimal("1500.00"),
        ),
    )

    inspections = await service.repository.list_measurement_item_inspections(
        company_id=company_id,
        measurement_item_id=item.id,
    )

    assert item.description == "ALVENARIA"
    assert item.service_template_id == template.id
    assert [
        (inspection.sequence_number, inspection.description, inspection.verification_method)
        for inspection in inspections
    ] == [
        (1, "LOCAÇÃO", "TRENA"),
        (2, "PRUMO", "RÉGUA"),
        (3, "ENCUNHAMENTO", "VISUAL"),
    ]


@pytest.mark.asyncio
async def test_the_same_service_cannot_be_measured_twice_in_one_measurement() -> None:
    service, company_id = build_service()
    content = build_caixa_spreadsheet(service_name="Alvenaria", items=[("Locação", "Trena")])
    await service.import_service_templates(company_id=company_id, files=[("alvenaria.xlsx", content)])
    template = (await service.list_service_templates(company_id=company_id))[0]
    measurement = await build_measurement_scenario(service=service, company_id=company_id)

    await service.create_measurement_item(
        company_id=company_id,
        measurement_id=measurement.id,
        request=ConstructionMeasurementItemCreate(service_template_id=template.id, amount=Decimal("100.00")),
    )

    with pytest.raises(ConstructionInvalidValueError) as error:
        await service.create_measurement_item(
            company_id=company_id,
            measurement_id=measurement.id,
            request=ConstructionMeasurementItemCreate(service_template_id=template.id, amount=Decimal("200.00")),
        )

    assert error.value.error_code == "CONSTRUCTION_MEASUREMENT_ITEM_DUPLICATE_SERVICE"


@pytest.mark.asyncio
async def test_item_without_description_or_template_is_refused() -> None:
    service, company_id = build_service()
    measurement = await build_measurement_scenario(service=service, company_id=company_id)

    with pytest.raises(ConstructionInvalidValueError) as error:
        await service.create_measurement_item(
            company_id=company_id,
            measurement_id=measurement.id,
            request=ConstructionMeasurementItemCreate(amount=Decimal("100.00")),
        )

    assert error.value.error_code == "CONSTRUCTION_MEASUREMENT_ITEM_DESCRIPTION_REQUIRED"


@pytest.mark.asyncio
async def test_future_start_date_is_refused() -> None:
    service, company_id = build_service()
    measurement = await build_measurement_scenario(service=service, company_id=company_id)

    with pytest.raises(ConstructionInvalidValueError) as error:
        await service.create_measurement_item(
            company_id=company_id,
            measurement_id=measurement.id,
            request=ConstructionMeasurementItemCreate(
                description="Servico futuro",
                amount=Decimal("100.00"),
                start_date=date(2099, 1, 1),
            ),
        )

    assert error.value.error_code == "CONSTRUCTION_INVALID_PERIOD"


@pytest.mark.asyncio
async def test_end_date_is_blocked_while_an_inspection_is_pending() -> None:
    service, company_id = build_service()
    content = build_caixa_spreadsheet(service_name="Alvenaria", items=[("Locação", "Trena")])
    await service.import_service_templates(company_id=company_id, files=[("alvenaria.xlsx", content)])
    template = (await service.list_service_templates(company_id=company_id))[0]
    measurement = await build_measurement_scenario(service=service, company_id=company_id)

    with pytest.raises(ConstructionInvalidValueError) as error:
        await service.create_measurement_item(
            company_id=company_id,
            measurement_id=measurement.id,
            request=ConstructionMeasurementItemCreate(
                service_template_id=template.id,
                amount=Decimal("100.00"),
                start_date=date(2026, 1, 10),
                end_date=date(2026, 1, 20),
            ),
        )

    assert error.value.error_code == "CONSTRUCTION_MEASUREMENT_ITEM_END_DATE_BLOCKED"


@pytest.mark.asyncio
async def test_renaming_a_template_to_an_existing_name_is_refused() -> None:
    service, company_id = build_service()
    first = build_caixa_spreadsheet(service_name="Alvenaria", items=[("Locação", "Trena")])
    second = build_caixa_spreadsheet(service_name="Cobertura", items=[("Telhas", "Visual")])
    await service.import_service_templates(
        company_id=company_id,
        files=[("alvenaria.xlsx", first), ("cobertura.xlsx", second)],
    )
    templates = await service.list_service_templates(company_id=company_id)
    cobertura = next(template for template in templates if template.name == "COBERTURA")

    with pytest.raises(Exception) as error:
        await service.update_service_template(
            company_id=company_id,
            service_template_id=cobertura.id,
            request=ConstructionServiceTemplateUpdate(name="Alvenaria"),
        )

    assert "ALVENARIA" in str(error.value)
