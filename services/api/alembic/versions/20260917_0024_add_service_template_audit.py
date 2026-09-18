"""record who created, changed, deactivated or deleted a catalog service

The FVS catalog only knew created_at/updated_at: no author anywhere, and DELETE
was physical. A sheet could be rewritten end to end, or vanish, leaving nothing
to answer "who did this" -- which is exactly what the Caixa asks the FVS to
prove.

Two things change. The template itself carries the author of the last write
(created_by/updated_by) plus a soft delete (deleted_at/deleted_by), and every
mutation also appends a row to construction_service_template_audits with the
full structure at that moment. The audit table is what survives a revision:
the columns on the template only ever hold the LAST author, and replacing a
sheet overwrites the previous one.

Soft delete forces the uniqueness to become partial. The old constraint on
(company_id, name) would keep a deleted service's name reserved forever, so it
becomes a unique INDEX with WHERE deleted_at IS NULL -- delete a service and
the name is free again, while two live services still cannot share it.

The backfill writes one `created` row per existing template using its own
created_at and a NULL actor. That is the honest record: the service existed at
that time and the author was never captured. Leaving the history empty would
read as "nothing ever happened to this sheet", which is worse.

Revision ID: 20260917_0024
Revises: 20260917_0023
Create Date: 2026-09-17 15:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260917_0024"
down_revision = "20260917_0023"
branch_labels = None
depends_on = None

SCHEMA_NAME = "construction"
TEMPLATE_TABLE = "construction_service_templates"
AUDIT_TABLE = "construction_service_template_audits"

OLD_NAME_CONSTRAINT = "uq_construction_service_templates_name"
LIVE_NAME_INDEX = "uq_construction_service_templates_live_name"


def upgrade() -> None:
    op.add_column(
        TEMPLATE_TABLE,
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        TEMPLATE_TABLE,
        sa.Column("updated_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        TEMPLATE_TABLE,
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        TEMPLATE_TABLE,
        sa.Column("deleted_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema=SCHEMA_NAME,
    )

    # A deleted service must release its name; two live ones still may not share it.
    op.drop_constraint(OLD_NAME_CONSTRAINT, TEMPLATE_TABLE, schema=SCHEMA_NAME, type_="unique")
    op.create_index(
        LIVE_NAME_INDEX,
        TEMPLATE_TABLE,
        ["company_id", "name"],
        unique=True,
        schema=SCHEMA_NAME,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        AUDIT_TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("service_template_id", postgresql.UUID(as_uuid=True), nullable=False),
        # The revision number of the sheet. Ordering by created_at alone is not
        # enough: now() is the TRANSACTION time in Postgres, so two events in one
        # transaction tie and the trail loses its order.
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        # Denormalized on purpose: the trail has to stay readable after a rename.
        sa.Column("service_template_name", sa.String(length=255), nullable=False),
        sa.Column("event", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_person_id", postgresql.UUID(as_uuid=True), nullable=True),
        # The name as of the event: the person may be renamed or leave the company.
        sa.Column("actor_name", sa.String(length=255), nullable=True),
        sa.Column("summary", sa.String(length=255), nullable=True),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["service_template_id"],
            [f"{SCHEMA_NAME}.{TEMPLATE_TABLE}.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "service_template_id",
            "sequence_number",
            name="uq_construction_service_template_audits_sequence",
        ),
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_construction_service_template_audits_company_id",
        AUDIT_TABLE,
        ["company_id"],
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_construction_service_template_audits_template",
        AUDIT_TABLE,
        ["service_template_id", "sequence_number"],
        schema=SCHEMA_NAME,
    )

    op.execute(
        sa.text(
            f"""
            INSERT INTO {SCHEMA_NAME}.{AUDIT_TABLE} (
                id, company_id, service_template_id, service_template_name,
                sequence_number, event, source, summary, created_at
            )
            SELECT
                gen_random_uuid(),
                t.company_id,
                t.id,
                t.name,
                1,
                'created',
                'migration',
                'Registro anterior à auditoria: autor não capturado.',
                t.created_at
            FROM {SCHEMA_NAME}.{TEMPLATE_TABLE} t
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_construction_service_template_audits_template", AUDIT_TABLE, schema=SCHEMA_NAME)
    op.drop_index("ix_construction_service_template_audits_company_id", AUDIT_TABLE, schema=SCHEMA_NAME)
    op.drop_table(AUDIT_TABLE, schema=SCHEMA_NAME)

    # The old constraint spans every row, so a soft-deleted service sharing a
    # name with a live one would refuse it. Those are gone as far as the user is
    # concerned -- the downgrade makes it physical, as the old schema had it.
    op.execute(
        sa.text(
            f"DELETE FROM {SCHEMA_NAME}.{TEMPLATE_TABLE} WHERE deleted_at IS NOT NULL"
        )
    )

    op.drop_index(LIVE_NAME_INDEX, TEMPLATE_TABLE, schema=SCHEMA_NAME)
    op.create_unique_constraint(
        OLD_NAME_CONSTRAINT,
        TEMPLATE_TABLE,
        ["company_id", "name"],
        schema=SCHEMA_NAME,
    )

    op.drop_column(TEMPLATE_TABLE, "deleted_by_user_id", schema=SCHEMA_NAME)
    op.drop_column(TEMPLATE_TABLE, "deleted_at", schema=SCHEMA_NAME)
    op.drop_column(TEMPLATE_TABLE, "updated_by_user_id", schema=SCHEMA_NAME)
    op.drop_column(TEMPLATE_TABLE, "created_by_user_id", schema=SCHEMA_NAME)
