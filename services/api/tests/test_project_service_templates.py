from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.exceptions import ConstructionInvalidValueError, ConstructionNotFoundError
from app.schemas.construction import ConstructionMeasurementItemCreate
from tests.test_service_templates import build_caixa_spreadsheet, build_measurement_scenario, build_service


async def import_catalog(service, company_id, *names):
    files = [
        (f"{name}.xlsx", build_caixa_spreadsheet(service_name=name, items=[("Locação", "Trena")]))
        for name in names
    ]
    await service.import_service_templates(company_id=company_id, files=files)
    return {template.name: template for template in await service.list_service_templates(company_id=company_id)}


@pytest.mark.asyncio
async def test_without_a_project_list_the_measurement_sees_the_whole_catalog() -> None:
    service, company_id = build_service()
    catalog = await import_catalog(service, company_id, "Alvenaria", "Reboco")
    measurement = await build_measurement_scenario(service=service, company_id=company_id)

    templates, restricted = await service.list_service_templates_for_project(
        company_id=company_id, project_id=measurement.project_id
    )
    item = await service.create_measurement_item(
        company_id=company_id,
        measurement_id=measurement.id,
        request=ConstructionMeasurementItemCreate(description="Limpeza final", amount=Decimal("100.00")),
    )

    assert restricted is False
    assert {template.name for template in templates} == set(catalog)
    assert item.description == "Limpeza final"


@pytest.mark.asyncio
async def test_with_a_project_list_only_the_linked_services_are_offered_and_accepted() -> None:
    service, company_id = build_service()
    catalog = await import_catalog(service, company_id, "Alvenaria", "Reboco")
    measurement = await build_measurement_scenario(service=service, company_id=company_id)
    project_id = measurement.project_id

    linked = await service.link_project_services(
        company_id=company_id, project_id=project_id, service_template_ids=[catalog["ALVENARIA"].id]
    )
    templates, restricted = await service.list_service_templates_for_project(company_id=company_id, project_id=project_id)

    assert [template.name for template in linked] == ["ALVENARIA"]
    assert restricted is True
    assert [template.name for template in templates] == ["ALVENARIA"]

    with pytest.raises(ConstructionInvalidValueError) as outside:
        await service.create_measurement_item(
            company_id=company_id,
            measurement_id=measurement.id,
            request=ConstructionMeasurementItemCreate(service_template_id=catalog["REBOCO"].id, amount=Decimal("10")),
        )
    assert outside.value.error_code == "CONSTRUCTION_MEASUREMENT_ITEM_SERVICE_NOT_IN_PROJECT"

    with pytest.raises(ConstructionInvalidValueError) as typed:
        await service.create_measurement_item(
            company_id=company_id,
            measurement_id=measurement.id,
            request=ConstructionMeasurementItemCreate(description="Serviço avulso", amount=Decimal("10")),
        )
    assert typed.value.error_code == "CONSTRUCTION_MEASUREMENT_ITEM_PROJECT_SERVICE_REQUIRED"

    item = await service.create_measurement_item(
        company_id=company_id,
        measurement_id=measurement.id,
        request=ConstructionMeasurementItemCreate(service_template_id=catalog["ALVENARIA"].id, amount=Decimal("10")),
    )
    assert item.service_template_id == catalog["ALVENARIA"].id


@pytest.mark.asyncio
async def test_linking_twice_does_not_duplicate_and_unlinking_frees_the_catalog() -> None:
    service, company_id = build_service()
    catalog = await import_catalog(service, company_id, "Alvenaria", "Reboco")
    measurement = await build_measurement_scenario(service=service, company_id=company_id)
    project_id = measurement.project_id
    alvenaria = catalog["ALVENARIA"].id

    await service.link_project_services(company_id=company_id, project_id=project_id, service_template_ids=[alvenaria])
    again = await service.link_project_services(
        company_id=company_id, project_id=project_id, service_template_ids=[alvenaria, alvenaria]
    )
    assert [template.name for template in again] == ["ALVENARIA"]

    await service.unlink_project_service(company_id=company_id, project_id=project_id, service_template_id=alvenaria)
    templates, restricted = await service.list_service_templates_for_project(company_id=company_id, project_id=project_id)
    assert restricted is False
    assert len(templates) == 2

    with pytest.raises(ConstructionNotFoundError):
        await service.unlink_project_service(company_id=company_id, project_id=project_id, service_template_id=alvenaria)


@pytest.mark.asyncio
async def test_inactive_service_cannot_be_linked_nor_measured() -> None:
    service, company_id = build_service()
    catalog = await import_catalog(service, company_id, "Alvenaria")
    measurement = await build_measurement_scenario(service=service, company_id=company_id)
    template = catalog["ALVENARIA"]
    template.is_active = False

    with pytest.raises(ConstructionInvalidValueError) as linking:
        await service.link_project_services(
            company_id=company_id, project_id=measurement.project_id, service_template_ids=[template.id]
        )
    with pytest.raises(ConstructionInvalidValueError) as measuring:
        await service.create_measurement_item(
            company_id=company_id,
            measurement_id=measurement.id,
            request=ConstructionMeasurementItemCreate(service_template_id=template.id, amount=Decimal("10")),
        )

    assert linking.value.error_code == "CONSTRUCTION_SERVICE_TEMPLATE_INACTIVE"
    assert measuring.value.error_code == "CONSTRUCTION_SERVICE_TEMPLATE_INACTIVE"


@pytest.mark.asyncio
async def test_importing_fvs_files_into_the_project_reuses_the_catalog_and_links() -> None:
    service, company_id = build_service()
    await import_catalog(service, company_id, "Alvenaria")
    measurement = await build_measurement_scenario(service=service, company_id=company_id)
    files = [
        ("alvenaria.xlsx", build_caixa_spreadsheet(service_name="Alvenaria", items=[("Prumo", "Régua")])),
        ("pintura.xlsx", build_caixa_spreadsheet(service_name="Pintura", items=[("Demãos", "Visual")])),
        ("vazio.xlsx", b"not a spreadsheet"),
    ]

    results = await service.import_project_services(
        company_id=company_id, project_id=measurement.project_id, files=files
    )

    assert [(result["status"], result["linked"]) for result in results] == [
        ("skipped", True),
        ("created", True),
        ("failed", False),
    ]
    assert len(await service.list_service_templates(company_id=company_id)) == 2
    linked = await service.list_project_services(company_id=company_id, project_id=measurement.project_id)
    assert [template.name for template in linked] == ["ALVENARIA", "PINTURA"]


@pytest.mark.asyncio
async def test_replacing_the_project_list_keeps_only_the_saved_selection() -> None:
    service, company_id = build_service()
    catalog = await import_catalog(service, company_id, "Alvenaria", "Reboco", "Pintura")
    measurement = await build_measurement_scenario(service=service, company_id=company_id)
    project_id = measurement.project_id

    await service.link_project_services(
        company_id=company_id, project_id=project_id, service_template_ids=[catalog["ALVENARIA"].id]
    )
    replaced = await service.replace_project_services(
        company_id=company_id,
        project_id=project_id,
        service_template_ids=[catalog["REBOCO"].id, catalog["PINTURA"].id, catalog["REBOCO"].id],
    )

    assert [template.name for template in replaced] == ["PINTURA", "REBOCO"]
    with pytest.raises(ConstructionInvalidValueError) as outside:
        await service.create_measurement_item(
            company_id=company_id,
            measurement_id=measurement.id,
            request=ConstructionMeasurementItemCreate(service_template_id=catalog["ALVENARIA"].id, amount=Decimal("10")),
        )
    assert outside.value.error_code == "CONSTRUCTION_MEASUREMENT_ITEM_SERVICE_NOT_IN_PROJECT"


@pytest.mark.asyncio
async def test_replacing_with_an_empty_list_frees_the_whole_catalog() -> None:
    service, company_id = build_service()
    catalog = await import_catalog(service, company_id, "Alvenaria", "Reboco")
    measurement = await build_measurement_scenario(service=service, company_id=company_id)
    project_id = measurement.project_id
    await service.link_project_services(
        company_id=company_id, project_id=project_id, service_template_ids=[catalog["ALVENARIA"].id]
    )

    replaced = await service.replace_project_services(company_id=company_id, project_id=project_id, service_template_ids=[])
    templates, restricted = await service.list_service_templates_for_project(company_id=company_id, project_id=project_id)

    assert replaced == []
    assert restricted is False
    assert len(templates) == 2


@pytest.mark.asyncio
async def test_replacing_keeps_an_already_linked_inactive_service_but_refuses_a_new_one() -> None:
    service, company_id = build_service()
    catalog = await import_catalog(service, company_id, "Alvenaria", "Reboco", "Pintura")
    measurement = await build_measurement_scenario(service=service, company_id=company_id)
    project_id = measurement.project_id
    await service.link_project_services(
        company_id=company_id, project_id=project_id, service_template_ids=[catalog["ALVENARIA"].id]
    )
    catalog["ALVENARIA"].is_active = False
    catalog["PINTURA"].is_active = False

    kept = await service.replace_project_services(
        company_id=company_id,
        project_id=project_id,
        service_template_ids=[catalog["ALVENARIA"].id, catalog["REBOCO"].id],
    )
    assert [template.name for template in kept] == ["ALVENARIA", "REBOCO"]

    with pytest.raises(ConstructionInvalidValueError) as inactive:
        await service.replace_project_services(
            company_id=company_id,
            project_id=project_id,
            service_template_ids=[catalog["PINTURA"].id],
        )
    assert inactive.value.error_code == "CONSTRUCTION_SERVICE_TEMPLATE_INACTIVE"
    unchanged = await service.list_project_services(company_id=company_id, project_id=project_id)
    assert [template.name for template in unchanged] == ["ALVENARIA", "REBOCO"]


@pytest.mark.asyncio
async def test_project_list_of_an_unknown_project_is_not_found() -> None:
    service, company_id = build_service()

    with pytest.raises(ConstructionNotFoundError):
        await service.list_project_services(company_id=company_id, project_id=uuid4())
