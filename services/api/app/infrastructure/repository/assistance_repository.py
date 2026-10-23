from sqlalchemy import MetaData, Table, Column, DateTime, String, Boolean, select, func, or_, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import load_only, raiseload, selectinload

from app.infrastructure.database.models.assistance import AssistanceRequest, AssistanceService, AssistanceComplaint
from app.infrastructure.database.models.construction import ConstructionProject, ConstructionUnit


persons = Table(
    "persons",
    MetaData(),
    Column("id", UUID(as_uuid=True)),
    Column("name", String),
    Column("is_active", Boolean),
    Column("deleted_at", DateTime(timezone=True)),
    schema="public",
)


person_roles = Table(
    "person_company_roles",
    persons.metadata,
    Column("person_id", UUID(as_uuid=True)),
    Column("company_id", UUID(as_uuid=True)),
    Column("role_type_id", UUID(as_uuid=True)),
    Column("is_active", Boolean),
    Column("deleted_at", DateTime(timezone=True)),
    schema="public",
)
person_profiles = Table(
    "person_company_profiles",
    persons.metadata,
    Column("person_id", UUID(as_uuid=True)),
    Column("company_id", UUID(as_uuid=True)),
    Column("is_active", Boolean),
    Column("deleted_at", DateTime(timezone=True)),
    schema="public",
)
person_access = Table(
    "person_companies",
    persons.metadata,
    Column("person_id", UUID(as_uuid=True)),
    Column("company_id", UUID(as_uuid=True)),
    Column("is_active", Boolean),
    Column("deleted_at", DateTime(timezone=True)),
    schema="public",
)
role_types = Table(
    "person_business_role_types",
    persons.metadata,
    Column("id", UUID(as_uuid=True)),
    Column("company_id", UUID(as_uuid=True)),
    Column("code", String),
    Column("is_active", Boolean),
    Column("deleted_at", DateTime(timezone=True)),
    schema="public",
)


class AssistanceRepository:
    def __init__(self, session, scope):
        self.session = session
        self.scope = scope

    def conditions(self, company_id):
        result = [AssistanceRequest.company_id == company_id, AssistanceRequest.deleted_at.is_(None)]
        if not self.scope.unrestricted:
            result.append(AssistanceRequest.project_id.in_(self.scope.project_ids))
        return result

    async def project(self, company_id, project_id, lock=False):
        query = select(ConstructionProject).where(
            ConstructionProject.company_id == company_id,
            ConstructionProject.id == project_id,
            ConstructionProject.deleted_at.is_(None),
        )
        if not self.scope.unrestricted:
            query = query.where(ConstructionProject.id.in_(self.scope.project_ids))
        if lock:
            query = query.with_for_update()
        return await self.session.scalar(query)

    async def unit(self, company_id, project_id, unit_id):
        return await self.session.scalar(
            select(ConstructionUnit)
            .where(
                ConstructionUnit.company_id == company_id,
                ConstructionUnit.project_id == project_id,
                ConstructionUnit.id == unit_id,
                ConstructionUnit.deleted_at.is_(None),
            )
            .with_for_update()
        )

    @staticmethod
    def company_person_ids(company_id):
        profiles = select(person_profiles.c.person_id).where(
            person_profiles.c.company_id == company_id,
            person_profiles.c.is_active.is_(True),
            person_profiles.c.deleted_at.is_(None),
        )
        access = select(person_access.c.person_id).where(
            person_access.c.company_id == company_id,
            person_access.c.is_active.is_(True),
            person_access.c.deleted_at.is_(None),
        )
        return profiles.union(access)

    async def valid_people(self, company_id, ids):
        return set(
            (
                await self.session.scalars(
                    select(persons.c.id).where(
                        persons.c.id.in_(ids),
                        persons.c.id.in_(self.company_person_ids(company_id)),
                        persons.c.deleted_at.is_(None),
                    )
                )
            ).all()
        )

    def employee_ids(self, company_id):
        return (
            select(person_roles.c.person_id)
            .join(
                role_types,
                role_types.c.id == person_roles.c.role_type_id,
            )
            .where(
                person_roles.c.company_id == company_id,
                person_roles.c.is_active.is_(True),
                person_roles.c.deleted_at.is_(None),
                role_types.c.code == "employee",
                role_types.c.is_active.is_(True),
                role_types.c.deleted_at.is_(None),
                or_(role_types.c.company_id.is_(None), role_types.c.company_id == company_id),
                person_roles.c.person_id.in_(self.company_person_ids(company_id)),
            )
        )

    async def print_branding(self, company_id):
        row = (
            (
                await self.session.execute(
                    text(
                        "SELECT legal_name,trade_name,logo_url FROM public.companies WHERE id=:company_id AND deleted_at IS NULL"
                    ),
                    {"company_id": company_id},
                )
            )
            .mappings()
            .first()
        )
        return {
            "company_name": (row["trade_name"] or row["legal_name"]) if row else None,
            "company_logo_url": row["logo_url"] if row else None,
        }

    async def print_location(self, company_id, project_id):
        project = await self.project(company_id, project_id)
        address = (project.address_json or {}) if project else {}
        city = address.get("city") or address.get("cidade") or address.get("localidade")
        zip_code = address.get("zip_code") or address.get("cep")
        city = city.strip() if isinstance(city, str) else None
        zip_code = str(zip_code) if zip_code else None
        if not city and zip_code:
            cities = (
                await self.session.scalars(
                    text(
                        "SELECT DISTINCT c.name FROM public.addresses a JOIN public.cities c ON c.id=a.city_id "
                        "WHERE regexp_replace(a.zip_code,'[^0-9]','','g')=:zip_code "
                        "AND a.deleted_at IS NULL AND c.deleted_at IS NULL LIMIT 2"
                    ),
                    {"zip_code": "".join(filter(str.isdigit, str(zip_code)))},
                )
            ).all()
            if len(cities) == 1:
                city = cities[0]
        return {"city": city, "zip_code": zip_code}

    async def print_people(self, row):
        ids = {row.customer_person_id, row.attendant_person_id, row.analyst_person_id}
        ids.update(c.analyzed_by_person_id for c in row.complaints if c.deleted_at is None)
        for service in row.services:
            if service.deleted_at is None:
                ids.update((service.executed_by_person_id, service.inspected_by_person_id))
        return dict(
            (
                await self.session.execute(
                    select(persons.c.id, persons.c.name).where(
                        persons.c.id.in_(ids - {None}),
                    )
                )
            ).all()
        )

    async def next_number(self, company_id, project_id):
        return (
            await self.session.scalar(
                select(func.max(AssistanceRequest.number))
                .where(AssistanceRequest.company_id == company_id, AssistanceRequest.project_id == project_id)
                .execution_options(include_deleted=True)
            )
            or 0
        ) + 1

    async def get(self, company_id, request_id, lock=False):
        query = select(AssistanceRequest).where(*self.conditions(company_id), AssistanceRequest.id == request_id)
        if lock:
            query = query.with_for_update()
        return await self.session.scalar(query.execution_options(populate_existing=True))

    async def list(self, company_id, filters, today, page, page_size):
        conditions = self.conditions(company_id)
        for key in ("project_id", "unit_id", "customer_person_id", "status"):
            if filters.get(key) is not None:
                conditions.append(getattr(AssistanceRequest, key) == filters[key])
        if filters.get("opened_from"):
            conditions.append(AssistanceRequest.opened_at >= filters["opened_from"])
        if filters.get("opened_to"):
            conditions.append(AssistanceRequest.opened_at <= filters["opened_to"])
        active_service = [AssistanceService.request_id == AssistanceRequest.id, AssistanceService.deleted_at.is_(None)]
        if filters.get("responsible_person_id"):
            person_id = filters["responsible_person_id"]
            conditions.append(
                or_(
                    AssistanceRequest.attendant_person_id == person_id,
                    AssistanceRequest.analyst_person_id == person_id,
                    select(1)
                    .where(
                        *active_service,
                        or_(
                            AssistanceService.executed_by_person_id == person_id,
                            AssistanceService.inspected_by_person_id == person_id,
                        ),
                    )
                    .exists(),
                    select(1)
                    .where(
                        AssistanceComplaint.request_id == AssistanceRequest.id,
                        AssistanceComplaint.deleted_at.is_(None),
                        AssistanceComplaint.analyzed_by_person_id == person_id,
                    )
                    .exists(),
                )
            )
        if filters.get("overdue") is not None:
            overdue = (
                select(1)
                .where(*active_service, AssistanceService.due_date < today, AssistanceService.executed_at.is_(None))
                .exists()
            )
            conditions.append(overdue if filters["overdue"] else ~overdue)
        total = await self.session.scalar(select(func.count()).select_from(AssistanceRequest).where(*conditions))
        rows = (
            await self.session.scalars(
                select(AssistanceRequest)
                .options(
                    load_only(
                        AssistanceRequest.id,
                        AssistanceRequest.company_id,
                        AssistanceRequest.project_id,
                        AssistanceRequest.unit_id,
                        AssistanceRequest.customer_person_id,
                        AssistanceRequest.attendant_person_id,
                        AssistanceRequest.analyst_person_id,
                        AssistanceRequest.number,
                        AssistanceRequest.status,
                        AssistanceRequest.opened_at,
                        AssistanceRequest.completed_at,
                    ),
                    raiseload(AssistanceRequest.contacts),
                    raiseload(AssistanceRequest.history),
                    selectinload(AssistanceRequest.complaints).load_only(
                        AssistanceComplaint.id,
                        AssistanceComplaint.deleted_at,
                        AssistanceComplaint.provenance,
                        AssistanceComplaint.analyzed_by_person_id,
                        AssistanceComplaint.analyzed_at,
                    ),
                    selectinload(AssistanceRequest.services).load_only(
                        AssistanceService.id,
                        AssistanceService.deleted_at,
                        AssistanceService.complaint_id,
                        AssistanceService.due_date,
                        AssistanceService.executed_at,
                        AssistanceService.executed_by_person_id,
                        AssistanceService.inspected_at,
                        AssistanceService.inspected_by_person_id,
                    ),
                )
                .where(*conditions)
                .order_by(AssistanceRequest.opened_at.desc(), AssistanceRequest.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        return rows, total

    async def labels(self, requests):
        projects = dict(
            (
                await self.session.execute(
                    select(ConstructionProject.id, ConstructionProject.name).where(
                        ConstructionProject.id.in_({r.project_id for r in requests})
                    )
                )
            ).all()
        )
        units = dict(
            (
                await self.session.execute(
                    select(ConstructionUnit.id, ConstructionUnit.code).where(
                        ConstructionUnit.id.in_({r.unit_id for r in requests})
                    )
                )
            ).all()
        )
        people = dict(
            (
                await self.session.execute(
                    select(persons.c.id, persons.c.name).where(
                        persons.c.id.in_(
                            {person_id for r in requests for person_id in (r.customer_person_id, r.attendant_person_id)}
                        )
                    )
                )
            ).all()
        )
        return projects, units, people

    def add(self, row):
        self.session.add(row)

    async def flush(self):
        await self.session.flush()

    async def refresh(self, row, attribute_names):
        await self.session.refresh(row, attribute_names=attribute_names)

    async def commit(self):
        await self.session.commit()

    async def release_operation(self, company_id):
        await self.session.execute(
            text(
                "INSERT INTO construction.assistance_migration_state(company_id, released_at) VALUES (:company_id, now()) ON CONFLICT (company_id) DO UPDATE SET released_at=coalesce(assistance_migration_state.released_at, now())"
            ),
            {"company_id": company_id},
        )

    async def references(self, company_id, kind, search, project_id, reference_id):
        if kind in ("person", "employee"):
            query = select(persons.c.id, persons.c.name).where(
                persons.c.deleted_at.is_(None),
                persons.c.id.in_(self.company_person_ids(company_id)),
            )
            if kind == "employee":
                query = query.where(persons.c.id.in_(self.employee_ids(company_id)), persons.c.is_active.is_(True))
            name = persons.c.name
            identifier = persons.c.id
        elif kind == "project":
            query = select(ConstructionProject.id, ConstructionProject.name).where(
                ConstructionProject.company_id == company_id, ConstructionProject.deleted_at.is_(None)
            )
            name = ConstructionProject.name
            identifier = ConstructionProject.id
            if not self.scope.unrestricted:
                query = query.where(ConstructionProject.id.in_(self.scope.project_ids))
        else:
            name = func.concat(ConstructionUnit.code, " - ", func.coalesce(persons.c.name, "Sem comprador vinculado"))
            query = (
                select(ConstructionUnit.id, name.label("name"), persons.c.id.label("buyer_person_id"))
                .outerjoin(persons, (persons.c.id == ConstructionUnit.buyer_person_id) & persons.c.deleted_at.is_(None))
                .where(ConstructionUnit.company_id == company_id, ConstructionUnit.deleted_at.is_(None))
            )
            identifier = ConstructionUnit.id
            if project_id:
                query = query.where(ConstructionUnit.project_id == project_id)
            if not self.scope.unrestricted:
                query = query.where(ConstructionUnit.project_id.in_(self.scope.project_ids))
        if reference_id:
            query = query.where(identifier == reference_id)
        elif search:
            query = query.where(name.ilike(f"%{search}%"))
        return [dict(r) for r in (await self.session.execute(query.order_by(name).limit(50))).mappings()]
