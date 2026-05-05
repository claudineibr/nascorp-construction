"""add measurement detail fields

Revision ID: 20260505_0008
Revises: 20260505_0007
Create Date: 2026-05-05 13:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260505_0008"
down_revision = "20260505_0007"
branch_labels = None
depends_on = None

SCHEMA_NAME = "construction"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        raise RuntimeError("Construction API migrations require PostgreSQL.")

    op.add_column(
        "construction_measurements",
        sa.Column("sequence_number", sa.Integer(), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        "construction_measurements",
        sa.Column("measurement_type", sa.String(length=30), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        "construction_measurements",
        sa.Column("competence_date", sa.Date(), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        "construction_measurements",
        sa.Column("gross_amount", sa.Numeric(14, 2), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        "construction_measurements",
        sa.Column("retentions_amount", sa.Numeric(14, 2), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        "construction_measurements",
        sa.Column("net_amount", sa.Numeric(14, 2), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        "construction_measurements",
        sa.Column("document_type", sa.String(length=40), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        "construction_measurements",
        sa.Column("document_number", sa.String(length=60), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        "construction_measurements",
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        schema=SCHEMA_NAME,
    )

    op.execute(
        """
        UPDATE construction.construction_measurements
        SET gross_amount = measured_amount,
            retentions_amount = COALESCE(retentions_amount, 0),
            net_amount = measured_amount
        WHERE gross_amount IS NULL OR net_amount IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("construction_measurements", "rejection_reason", schema=SCHEMA_NAME)
    op.drop_column("construction_measurements", "document_number", schema=SCHEMA_NAME)
    op.drop_column("construction_measurements", "document_type", schema=SCHEMA_NAME)
    op.drop_column("construction_measurements", "net_amount", schema=SCHEMA_NAME)
    op.drop_column("construction_measurements", "retentions_amount", schema=SCHEMA_NAME)
    op.drop_column("construction_measurements", "gross_amount", schema=SCHEMA_NAME)
    op.drop_column("construction_measurements", "competence_date", schema=SCHEMA_NAME)
    op.drop_column("construction_measurements", "measurement_type", schema=SCHEMA_NAME)
    op.drop_column("construction_measurements", "sequence_number", schema=SCHEMA_NAME)
