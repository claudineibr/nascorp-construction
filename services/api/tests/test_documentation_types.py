from uuid import uuid4

import pytest

from app.domain.exceptions import ConstructionDuplicateCodeError, ConstructionNotFoundError
from app.domain.services import ConstructionProjectService
from app.schemas.construction import (
    ConstructionDocumentationTypeCreate,
    ConstructionDocumentationTypeUpdate,
)
from tests.test_construction_project_service import FakeConstructionRepository


async def test_listing_seeds_the_four_legacy_types_for_a_company_without_catalog() -> None:
    company_id = uuid4()
    repository = FakeConstructionRepository()
    service = ConstructionProjectService(repository=repository)

    documentation_types = await service.list_documentation_types(company_id=company_id)

    assert [documentation_type.system_code for documentation_type in documentation_types] == [
        "APPRAISAL",
        "NOTARY",
        "IPTU",
        "CITY_HALL",
    ]
    assert [documentation_type.name for documentation_type in documentation_types] == [
        "Avaliação",
        "Cartório",
        "IPTU",
        "Prefeitura",
    ]


async def test_renaming_a_seeded_type_does_not_make_the_seed_create_it_again() -> None:
    company_id = uuid4()
    repository = FakeConstructionRepository()
    service = ConstructionProjectService(repository=repository)

    seeded = await service.list_documentation_types(company_id=company_id)
    appraisal = next(item for item in seeded if item.system_code == "APPRAISAL")
    await service.update_documentation_type(
        company_id=company_id,
        documentation_type_id=appraisal.id,
        request=ConstructionDocumentationTypeUpdate(name="Laudo de avaliação"),
    )

    documentation_types = await service.list_documentation_types(company_id=company_id)

    assert len(documentation_types) == 4
    assert "Laudo de avaliação" in [item.name for item in documentation_types]
    assert "Avaliação" not in [item.name for item in documentation_types]


async def test_creating_an_existing_type_returns_it_instead_of_duplicating() -> None:
    company_id = uuid4()
    repository = FakeConstructionRepository()
    service = ConstructionProjectService(repository=repository)
    first = await service.create_documentation_type(
        company_id=company_id,
        request=ConstructionDocumentationTypeCreate(name="Seg. Caixa"),
    )

    second = await service.create_documentation_type(
        company_id=company_id,
        request=ConstructionDocumentationTypeCreate(name="  seg.   CAIXA  "),
    )

    assert second.id == first.id
    assert len(repository.documentation_types) == 1


async def test_creating_an_inactive_type_reactivates_it() -> None:
    company_id = uuid4()
    repository = FakeConstructionRepository()
    service = ConstructionProjectService(repository=repository)
    created = await service.create_documentation_type(
        company_id=company_id,
        request=ConstructionDocumentationTypeCreate(name="SANESUL"),
    )
    await service.update_documentation_type(
        company_id=company_id,
        documentation_type_id=created.id,
        request=ConstructionDocumentationTypeUpdate(is_active=False),
    )

    reactivated = await service.create_documentation_type(
        company_id=company_id,
        request=ConstructionDocumentationTypeCreate(name="sanesul"),
    )

    assert reactivated.id == created.id
    assert reactivated.is_active is True


async def test_renaming_onto_an_existing_name_is_refused() -> None:
    company_id = uuid4()
    repository = FakeConstructionRepository()
    service = ConstructionProjectService(repository=repository)
    await service.create_documentation_type(
        company_id=company_id,
        request=ConstructionDocumentationTypeCreate(name="SANESUL"),
    )
    other = await service.create_documentation_type(
        company_id=company_id,
        request=ConstructionDocumentationTypeCreate(name="Energisa"),
    )

    with pytest.raises(ConstructionDuplicateCodeError):
        await service.update_documentation_type(
            company_id=company_id,
            documentation_type_id=other.id,
            request=ConstructionDocumentationTypeUpdate(name="sanesul"),
        )


async def test_updating_a_type_from_another_company_is_not_found() -> None:
    repository = FakeConstructionRepository()
    service = ConstructionProjectService(repository=repository)
    created = await service.create_documentation_type(
        company_id=uuid4(),
        request=ConstructionDocumentationTypeCreate(name="SANESUL"),
    )

    with pytest.raises(ConstructionNotFoundError):
        await service.update_documentation_type(
            company_id=uuid4(),
            documentation_type_id=created.id,
            request=ConstructionDocumentationTypeUpdate(name="Outro"),
        )


async def test_search_filters_the_catalog_by_name() -> None:
    company_id = uuid4()
    repository = FakeConstructionRepository()
    service = ConstructionProjectService(repository=repository)
    await service.create_documentation_type(
        company_id=company_id,
        request=ConstructionDocumentationTypeCreate(name="SANESUL"),
    )

    documentation_types = await service.list_documentation_types(company_id=company_id, search="cart")

    assert [item.name for item in documentation_types] == ["Cartório"]


async def test_inactive_types_are_hidden_from_the_combobox_but_listed_when_asked() -> None:
    company_id = uuid4()
    repository = FakeConstructionRepository()
    service = ConstructionProjectService(repository=repository)
    created = await service.create_documentation_type(
        company_id=company_id,
        request=ConstructionDocumentationTypeCreate(name="SANESUL"),
    )
    await service.update_documentation_type(
        company_id=company_id,
        documentation_type_id=created.id,
        request=ConstructionDocumentationTypeUpdate(is_active=False),
    )

    active_names = [item.name for item in await service.list_documentation_types(company_id=company_id)]
    all_names = [
        item.name
        for item in await service.list_documentation_types(company_id=company_id, only_active=False)
    ]

    assert "SANESUL" not in active_names
    assert "SANESUL" in all_names


async def test_deactivating_a_type_without_renaming_it_does_not_wipe_the_name() -> None:
    company_id = uuid4()
    repository = FakeConstructionRepository()
    service = ConstructionProjectService(repository=repository)
    created = await service.create_documentation_type(
        company_id=company_id,
        request=ConstructionDocumentationTypeCreate(name="SANESUL"),
    )

    updated = await service.update_documentation_type(
        company_id=company_id,
        documentation_type_id=created.id,
        request=ConstructionDocumentationTypeUpdate(name=None, is_active=False),
    )

    assert updated.name == "SANESUL"
    assert updated.normalized_name == "SANESUL"
    assert updated.is_active is False


async def test_the_seed_adopts_a_type_the_company_had_already_created_by_hand() -> None:
    company_id = uuid4()
    repository = FakeConstructionRepository()
    service = ConstructionProjectService(repository=repository)
    handmade = await service.create_documentation_type(
        company_id=company_id,
        request=ConstructionDocumentationTypeCreate(name="Cartório"),
    )

    documentation_types = await service.list_documentation_types(company_id=company_id)

    assert len(documentation_types) == 4
    assert handmade.system_code == "NOTARY"
    assert len([item for item in documentation_types if item.system_code == "NOTARY"]) == 1


async def test_the_seed_does_not_rerun_once_every_system_code_exists() -> None:
    company_id = uuid4()
    repository = FakeConstructionRepository()
    service = ConstructionProjectService(repository=repository)

    await service.list_documentation_types(company_id=company_id)
    commits_after_seed = repository.commits
    await service.list_documentation_types(company_id=company_id)

    assert repository.commits == commits_after_seed
