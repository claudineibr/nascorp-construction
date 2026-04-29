"""create event foundation

Revision ID: 20260428_0001
Revises:
Create Date: 2026-04-28 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260428_0001"
down_revision = None
branch_labels = None
depends_on = None

SCHEMA_NAME = "construction"
EVENT_STATUS_PENDING = "pending"
DEFAULT_RETRY_COUNT = "0"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        raise RuntimeError("Construction API migrations require PostgreSQL.")

    op.execute(sa.text(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA_NAME}"'))

    op.create_table(
        "outbox_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("event_version", sa.Integer(), nullable=False),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("aggregate_type", sa.String(length=120), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("producer", sa.String(length=120), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("causation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default=EVENT_STATUS_PENDING),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default=DEFAULT_RETRY_COUNT),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.create_index("ix_outbox_events_status_occurred_at", "outbox_events", ["status", "occurred_at"], schema=SCHEMA_NAME)
    op.create_index("ix_outbox_events_company_id", "outbox_events", ["company_id"], schema=SCHEMA_NAME)
    op.create_index("uq_outbox_events_event_id", "outbox_events", ["event_id"], unique=True, schema=SCHEMA_NAME)

    op.create_table(
        "processed_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("consumer_name", sa.String(length=120), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "uq_processed_events_consumer_event",
        "processed_events",
        ["consumer_name", "event_id"],
        unique=True,
        schema=SCHEMA_NAME,
    )

    op.create_table(
        "dead_letter_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("event_version", sa.Integer(), nullable=False),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("aggregate_type", sa.String(length=120), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("producer", sa.String(length=120), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("causation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default=DEFAULT_RETRY_COUNT),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=SCHEMA_NAME,
    )
    op.create_index("ix_dead_letter_events_event_id", "dead_letter_events", ["event_id"], schema=SCHEMA_NAME)
    op.create_index("ix_dead_letter_events_company_id", "dead_letter_events", ["company_id"], schema=SCHEMA_NAME)


def downgrade() -> None:
    op.drop_index("ix_dead_letter_events_company_id", table_name="dead_letter_events", schema=SCHEMA_NAME)
    op.drop_index("ix_dead_letter_events_event_id", table_name="dead_letter_events", schema=SCHEMA_NAME)
    op.drop_table("dead_letter_events", schema=SCHEMA_NAME)
    op.drop_index("uq_processed_events_consumer_event", table_name="processed_events", schema=SCHEMA_NAME)
    op.drop_table("processed_events", schema=SCHEMA_NAME)
    op.drop_index("uq_outbox_events_event_id", table_name="outbox_events", schema=SCHEMA_NAME)
    op.drop_index("ix_outbox_events_company_id", table_name="outbox_events", schema=SCHEMA_NAME)
    op.drop_index("ix_outbox_events_status_occurred_at", table_name="outbox_events", schema=SCHEMA_NAME)
    op.drop_table("outbox_events", schema=SCHEMA_NAME)