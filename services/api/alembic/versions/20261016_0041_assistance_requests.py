"""assistance_requests

Revision ID: 20261016_0041
Revises: 20261015_0040
Create Date: 2026-10-16 21:52:34.633971
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261016_0041"
down_revision = "20261015_0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistance_migration_state",
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("company_id", name=op.f("pk_assistance_migration_state")),
        schema="construction",
    )
    op.create_table(
        "assistance_requests",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("unit_id", sa.UUID(), nullable=False),
        sa.Column("customer_person_id", sa.UUID(), nullable=False),
        sa.Column("attendant_person_id", sa.UUID(), nullable=False),
        sa.Column("analyst_person_id", sa.UUID(), nullable=True),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("legacy_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["construction.construction_projects.id"],
            name=op.f("fk_assistance_requests_project_id_construction_projects"),
        ),
        sa.ForeignKeyConstraint(
            ["unit_id"],
            ["construction.construction_units.id"],
            name=op.f("fk_assistance_requests_unit_id_construction_units"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assistance_requests")),
        sa.UniqueConstraint("company_id", "project_id", "number", name=op.f("uq_assistance_requests_company_id")),
        sa.UniqueConstraint("source_id", name=op.f("uq_assistance_requests_source_id")),
        schema="construction",
    )
    op.create_index(
        op.f("ix_construction_assistance_requests_analyst_person_id"),
        "assistance_requests",
        ["analyst_person_id"],
        unique=False,
        schema="construction",
    )
    op.create_index(
        op.f("ix_construction_assistance_requests_attendant_person_id"),
        "assistance_requests",
        ["attendant_person_id"],
        unique=False,
        schema="construction",
    )
    op.create_index(
        op.f("ix_construction_assistance_requests_company_id"),
        "assistance_requests",
        ["company_id"],
        unique=False,
        schema="construction",
    )
    op.create_index(
        op.f("ix_construction_assistance_requests_customer_person_id"),
        "assistance_requests",
        ["customer_person_id"],
        unique=False,
        schema="construction",
    )
    op.create_index(
        op.f("ix_construction_assistance_requests_project_id"),
        "assistance_requests",
        ["project_id"],
        unique=False,
        schema="construction",
    )
    op.create_index(
        op.f("ix_construction_assistance_requests_unit_id"),
        "assistance_requests",
        ["unit_id"],
        unique=False,
        schema="construction",
    )
    op.create_table(
        "assistance_complaints",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("request_id", sa.UUID(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("provenance", sa.String(length=20), nullable=False),
        sa.Column("analyzed_by_person_id", sa.UUID(), nullable=True),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("original_number", sa.Integer(), nullable=True),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("legacy_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["construction.assistance_requests.id"],
            name=op.f("fk_assistance_complaints_request_id_assistance_requests"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assistance_complaints")),
        sa.UniqueConstraint("source_id", name=op.f("uq_assistance_complaints_source_id")),
        schema="construction",
    )
    op.create_index(
        op.f("ix_construction_assistance_complaints_analyzed_by_person_id"),
        "assistance_complaints",
        ["analyzed_by_person_id"],
        unique=False,
        schema="construction",
    )
    op.create_index(
        op.f("ix_construction_assistance_complaints_request_id"),
        "assistance_complaints",
        ["request_id"],
        unique=False,
        schema="construction",
    )
    op.create_table(
        "assistance_contacts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("request_id", sa.UUID(), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["construction.assistance_requests.id"],
            name=op.f("fk_assistance_contacts_request_id_assistance_requests"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assistance_contacts")),
        schema="construction",
    )
    op.create_index(
        op.f("ix_construction_assistance_contacts_request_id"),
        "assistance_contacts",
        ["request_id"],
        unique=False,
        schema="construction",
    )
    op.create_table(
        "assistance_history",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("request_id", sa.UUID(), nullable=False),
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["construction.assistance_requests.id"],
            name=op.f("fk_assistance_history_request_id_assistance_requests"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assistance_history")),
        schema="construction",
    )
    op.create_index(
        op.f("ix_construction_assistance_history_actor_user_id"),
        "assistance_history",
        ["actor_user_id"],
        unique=False,
        schema="construction",
    )
    op.create_index(
        op.f("ix_construction_assistance_history_request_id"),
        "assistance_history",
        ["request_id"],
        unique=False,
        schema="construction",
    )
    op.create_table(
        "assistance_services",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("request_id", sa.UUID(), nullable=False),
        sa.Column("complaint_id", sa.UUID(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("executed_by_person_id", sa.UUID(), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("inspected_by_person_id", sa.UUID(), nullable=True),
        sa.Column("inspected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("original_number", sa.Integer(), nullable=True),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("legacy_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["complaint_id"],
            ["construction.assistance_complaints.id"],
            name=op.f("fk_assistance_services_complaint_id_assistance_complaints"),
        ),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["construction.assistance_requests.id"],
            name=op.f("fk_assistance_services_request_id_assistance_requests"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assistance_services")),
        sa.UniqueConstraint("source_id", name=op.f("uq_assistance_services_source_id")),
        schema="construction",
    )
    op.create_index(
        op.f("ix_construction_assistance_services_complaint_id"),
        "assistance_services",
        ["complaint_id"],
        unique=False,
        schema="construction",
    )
    op.create_index(
        op.f("ix_construction_assistance_services_executed_by_person_id"),
        "assistance_services",
        ["executed_by_person_id"],
        unique=False,
        schema="construction",
    )
    op.create_index(
        op.f("ix_construction_assistance_services_inspected_by_person_id"),
        "assistance_services",
        ["inspected_by_person_id"],
        unique=False,
        schema="construction",
    )
    op.create_index(
        op.f("ix_construction_assistance_services_request_id"),
        "assistance_services",
        ["request_id"],
        unique=False,
        schema="construction",
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_construction_assistance_services_request_id"), table_name="assistance_services", schema="construction"
    )
    op.drop_index(
        op.f("ix_construction_assistance_services_inspected_by_person_id"),
        table_name="assistance_services",
        schema="construction",
    )
    op.drop_index(
        op.f("ix_construction_assistance_services_executed_by_person_id"),
        table_name="assistance_services",
        schema="construction",
    )
    op.drop_index(
        op.f("ix_construction_assistance_services_complaint_id"), table_name="assistance_services", schema="construction"
    )
    op.drop_table("assistance_services", schema="construction")
    op.drop_index(
        op.f("ix_construction_assistance_history_request_id"), table_name="assistance_history", schema="construction"
    )
    op.drop_index(
        op.f("ix_construction_assistance_history_actor_user_id"), table_name="assistance_history", schema="construction"
    )
    op.drop_table("assistance_history", schema="construction")
    op.drop_index(
        op.f("ix_construction_assistance_contacts_request_id"), table_name="assistance_contacts", schema="construction"
    )
    op.drop_table("assistance_contacts", schema="construction")
    op.drop_index(
        op.f("ix_construction_assistance_complaints_request_id"), table_name="assistance_complaints", schema="construction"
    )
    op.drop_index(
        op.f("ix_construction_assistance_complaints_analyzed_by_person_id"),
        table_name="assistance_complaints",
        schema="construction",
    )
    op.drop_table("assistance_complaints", schema="construction")
    op.drop_index(
        op.f("ix_construction_assistance_requests_unit_id"), table_name="assistance_requests", schema="construction"
    )
    op.drop_index(
        op.f("ix_construction_assistance_requests_project_id"), table_name="assistance_requests", schema="construction"
    )
    op.drop_index(
        op.f("ix_construction_assistance_requests_customer_person_id"),
        table_name="assistance_requests",
        schema="construction",
    )
    op.drop_index(
        op.f("ix_construction_assistance_requests_company_id"), table_name="assistance_requests", schema="construction"
    )
    op.drop_index(
        op.f("ix_construction_assistance_requests_attendant_person_id"),
        table_name="assistance_requests",
        schema="construction",
    )
    op.drop_index(
        op.f("ix_construction_assistance_requests_analyst_person_id"),
        table_name="assistance_requests",
        schema="construction",
    )
    op.drop_table("assistance_requests", schema="construction")
    op.drop_table("assistance_migration_state", schema="construction")
