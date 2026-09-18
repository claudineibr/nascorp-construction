"""turn the second FVS check into a reinspection, recorded as N rounds

The ERP read the second column of the Caixa FVS as a mandatory double check by
two different users. It is not: it is the REINSPECTION, and it is required when
the line failed. The old shape also had holes -- a failed line could never come
back (any non_compliant marked the item forever), a fully failed item still
accepted an end date, and submit/approve looked at no inspection at all.

Two fixed columns cannot hold "failed, fixed, reinspected, failed again", so
each verification becomes a row in construction_inspection_rounds. The table is
append-only and has no updated_at on purpose: correcting a round means recording
another one beside it.

`pending` stops being a stored value and becomes the ABSENCE of a round. That is
what kills the current bug where the client can post status="pending" and store a
pending verification. A CHECK constraint enforces it.

A round can also be `waived`: the line failed and the reinspection is impossible
-- the service left the contract, the wall was already plastered. Without it the
first real deadlock in production gets solved with an UPDATE in the database.

The backfill projects first_status/second_status into rounds 1 and 2, then
recomputes construction_measurement_items.inspection_status WITH THE NEW RULE.
That last step is not optional: under the old rule first=compliant with
second=pending meant `pending`, and under the new one it means `compliant`.
Skipping it would leave those items stuck in pending, never releasing end_date.

What the downgrade loses, and cannot recover: every round from sequence_number 3
on; comment, inspector_name, inspected_on, source and is_inferred of ALL rounds;
occurrences.inspection_id; and the distinction between "failed, awaiting
reinspection" and "awaiting the second check". A `waived` round comes back as the
literal string in first_status/second_status and reads as `pending` to the old
rollup rule.

Revision ID: 20260917_0025
Revises: 20260917_0024
Create Date: 2026-09-17 18:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260917_0025"
down_revision = "20260917_0024"
branch_labels = None
depends_on = None

SCHEMA_NAME = "construction"
ROUND_TABLE = "construction_inspection_rounds"
INSPECTION_TABLE = "construction_measurement_item_inspections"
ITEM_TABLE = "construction_measurement_items"
OCCURRENCE_TABLE = "construction_measurement_item_occurrences"

LEGACY_COLUMNS = (
    "first_status",
    "first_status_at",
    "first_status_by_user_id",
    "second_status",
    "second_status_at",
    "second_status_by_user_id",
)


def upgrade() -> None:
    op.create_table(
        ROUND_TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("inspection_id", postgresql.UUID(as_uuid=True), nullable=False),
        # Denormalized: saves a join on the submit/approve blocker, which runs
        # over a whole measurement, and never changes.
        sa.Column("measurement_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("inspected_on", sa.Date(), nullable=True),
        sa.Column("inspector_person_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("inspector_name", sa.String(length=255), nullable=True),
        sa.Column("recorded_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("recorded_by_name", sa.String(length=255), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("is_inferred", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["inspection_id"],
            [f"{SCHEMA_NAME}.{INSPECTION_TABLE}.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["measurement_item_id"],
            [f"{SCHEMA_NAME}.{ITEM_TABLE}.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "inspection_id",
            "sequence_number",
            name="uq_construction_inspection_rounds_sequence",
        ),
        sa.CheckConstraint(
            "status IN ('compliant', 'non_compliant', 'waived')",
            name="ck_construction_inspection_rounds_status",
        ),
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_construction_inspection_rounds_company_id",
        ROUND_TABLE,
        ["company_id"],
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_construction_inspection_rounds_inspection",
        ROUND_TABLE,
        ["inspection_id", "sequence_number"],
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_construction_inspection_rounds_item",
        ROUND_TABLE,
        ["measurement_item_id"],
        schema=SCHEMA_NAME,
    )

    op.add_column(
        INSPECTION_TABLE,
        sa.Column("status", sa.String(length=30), nullable=False, server_default=sa.text("'pending'")),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        INSPECTION_TABLE,
        sa.Column("rounds_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        INSPECTION_TABLE,
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA_NAME,
    )

    op.add_column(
        OCCURRENCE_TABLE,
        sa.Column("inspection_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.create_foreign_key(
        "fk_construction_occurrences_inspection",
        OCCURRENCE_TABLE,
        INSPECTION_TABLE,
        ["inspection_id"],
        ["id"],
        source_schema=SCHEMA_NAME,
        referent_schema=SCHEMA_NAME,
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_construction_occurrences_inspection",
        OCCURRENCE_TABLE,
        ["inspection_id"],
        schema=SCHEMA_NAME,
    )
    # No backfill for the link: nothing tied an occurrence to an inspection
    # before, and NULL is the honest record of that.

    # Round 1 for everyone, then round 2 for everyone: two separate statements
    # respect the unique regardless of the plan Postgres picks.
    for sequence_number, status_column, at_column, user_column in (
        (1, "first_status", "first_status_at", "first_status_by_user_id"),
        (2, "second_status", "second_status_at", "second_status_by_user_id"),
    ):
        fallback_at = "i.first_status_at, i.created_at" if sequence_number == 2 else "i.created_at"
        op.execute(
            sa.text(
                f"""
                INSERT INTO {SCHEMA_NAME}.{ROUND_TABLE} (
                    id, company_id, inspection_id, measurement_item_id, sequence_number,
                    status, verified_at, inspector_person_id, recorded_by_user_id,
                    source, created_at
                )
                SELECT
                    gen_random_uuid(),
                    i.company_id,
                    i.id,
                    i.measurement_item_id,
                    {sequence_number},
                    i.{status_column},
                    COALESCE(i.{at_column}, {fallback_at}),
                    i.inspector_person_id,
                    i.{user_column},
                    'migration',
                    COALESCE(i.{at_column}, {fallback_at})
                FROM {SCHEMA_NAME}.{INSPECTION_TABLE} i
                WHERE i.{status_column} <> 'pending'
                """
            )
        )

    op.execute(
        sa.text(
            f"""
            UPDATE {SCHEMA_NAME}.{INSPECTION_TABLE} i
               SET rounds_count = r.rounds_count,
                   status = r.last_status,
                   last_verified_at = r.last_verified_at
              FROM (
                    SELECT DISTINCT ON (inspection_id)
                           inspection_id,
                           status AS last_status,
                           verified_at AS last_verified_at,
                           COUNT(*) OVER (PARTITION BY inspection_id) AS rounds_count
                      FROM {SCHEMA_NAME}.{ROUND_TABLE}
                     ORDER BY inspection_id, sequence_number DESC
                   ) r
             WHERE r.inspection_id = i.id
            """
        )
    )

    # The new rollup rule. Without this, every item that was
    # (first=compliant, second=pending) stays `pending` forever and never
    # releases its end date.
    op.execute(
        sa.text(
            f"""
            UPDATE {SCHEMA_NAME}.{ITEM_TABLE} it
               SET inspection_status = s.next_status
              FROM (
                    SELECT ins.measurement_item_id AS item_id,
                           CASE
                               WHEN bool_or(ins.status = 'non_compliant') THEN 'non_compliant'
                               WHEN bool_or(ins.status = 'pending') THEN 'pending'
                               ELSE 'compliant'
                           END AS next_status
                      FROM {SCHEMA_NAME}.{INSPECTION_TABLE} ins
                     GROUP BY ins.measurement_item_id
                   ) s
             WHERE s.item_id = it.id
            """
        )
    )

    for column_name in LEGACY_COLUMNS:
        op.drop_column(INSPECTION_TABLE, column_name, schema=SCHEMA_NAME)


def downgrade() -> None:
    op.add_column(
        INSPECTION_TABLE,
        sa.Column("first_status", sa.String(length=30), nullable=False, server_default=sa.text("'pending'")),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        INSPECTION_TABLE,
        sa.Column("first_status_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        INSPECTION_TABLE,
        sa.Column("first_status_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        INSPECTION_TABLE,
        sa.Column("second_status", sa.String(length=30), nullable=False, server_default=sa.text("'pending'")),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        INSPECTION_TABLE,
        sa.Column("second_status_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        INSPECTION_TABLE,
        sa.Column("second_status_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema=SCHEMA_NAME,
    )

    # Rounds 3+ have nowhere to go and are dropped with the table.
    for sequence_number, prefix in ((1, "first"), (2, "second")):
        op.execute(
            sa.text(
                f"""
                UPDATE {SCHEMA_NAME}.{INSPECTION_TABLE} i
                   SET {prefix}_status = r.status,
                       {prefix}_status_at = r.verified_at,
                       {prefix}_status_by_user_id = r.recorded_by_user_id
                  FROM {SCHEMA_NAME}.{ROUND_TABLE} r
                 WHERE r.inspection_id = i.id
                   AND r.sequence_number = {sequence_number}
                """
            )
        )

    op.execute(
        sa.text(
            f"""
            UPDATE {SCHEMA_NAME}.{ITEM_TABLE} it
               SET inspection_status = s.next_status
              FROM (
                    SELECT ins.measurement_item_id AS item_id,
                           CASE
                               WHEN bool_or(
                                    ins.first_status = 'non_compliant'
                                 OR ins.second_status = 'non_compliant'
                               ) THEN 'non_compliant'
                               WHEN bool_and(
                                    ins.first_status = 'compliant'
                                AND ins.second_status = 'compliant'
                               ) THEN 'compliant'
                               ELSE 'pending'
                           END AS next_status
                      FROM {SCHEMA_NAME}.{INSPECTION_TABLE} ins
                     GROUP BY ins.measurement_item_id
                   ) s
             WHERE s.item_id = it.id
            """
        )
    )

    op.drop_index("ix_construction_occurrences_inspection", OCCURRENCE_TABLE, schema=SCHEMA_NAME)
    op.drop_constraint(
        "fk_construction_occurrences_inspection",
        OCCURRENCE_TABLE,
        schema=SCHEMA_NAME,
        type_="foreignkey",
    )
    op.drop_column(OCCURRENCE_TABLE, "inspection_id", schema=SCHEMA_NAME)

    op.drop_column(INSPECTION_TABLE, "last_verified_at", schema=SCHEMA_NAME)
    op.drop_column(INSPECTION_TABLE, "rounds_count", schema=SCHEMA_NAME)
    op.drop_column(INSPECTION_TABLE, "status", schema=SCHEMA_NAME)

    op.drop_index("ix_construction_inspection_rounds_item", ROUND_TABLE, schema=SCHEMA_NAME)
    op.drop_index("ix_construction_inspection_rounds_inspection", ROUND_TABLE, schema=SCHEMA_NAME)
    op.drop_index("ix_construction_inspection_rounds_company_id", ROUND_TABLE, schema=SCHEMA_NAME)
    op.drop_table(ROUND_TABLE, schema=SCHEMA_NAME)
