from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261111_0059"
down_revision = "20261110_0058"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("construction_units", "construction_unit_sales"):
        op.add_column(table, sa.Column("delivery_date", sa.Date(), nullable=True), schema="construction")
    op.create_table(
        "construction_unit_delivery_audits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("unit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sale_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("previous_date", sa.Date(), nullable=True),
        sa.Column("delivery_date", sa.Date(), nullable=True),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="construction",
    )
    for column in ("company_id", "unit_id"):
        op.create_index(f"ix_construction_construction_unit_delivery_audits_{column}",
                        "construction_unit_delivery_audits", [column], schema="construction")
    connection = op.get_bind()
    company_table = connection.scalar(sa.text("SELECT to_regclass('public.companies')"))
    for table in ("construction_units", "construction_unit_sales"):
        if company_table is None:
            if connection.scalar(sa.text(f"SELECT count(*) FROM construction.{table} WHERE delivered_at IS NOT NULL")):
                raise RuntimeError("A conversão das datas de entrega exige o cadastro e o fuso das empresas.")
            continue
        unit_id = "u.id" if table == "construction_units" else "u.unit_id"
        sale_id = "NULL::uuid" if table == "construction_units" else "u.id"
        connection.execute(sa.text(f"""INSERT INTO construction.construction_unit_delivery_audits
            (id,company_id,unit_id,sale_id,previous_date,delivery_date,reason)
            SELECT gen_random_uuid(),u.company_id,{unit_id},{sale_id},NULL,
                (u.delivered_at AT TIME ZONE c.timezone)::date,'BACKFILL_CALENDAR_DATE'
            FROM construction.{table} u JOIN public.companies c ON c.id=u.company_id
            WHERE u.delivered_at IS NOT NULL AND u.delivery_date IS NULL"""))
        connection.execute(sa.text(f"""UPDATE construction.{table} u
            SET delivery_date=(u.delivered_at AT TIME ZONE c.timezone)::date
            FROM public.companies c WHERE c.id=u.company_id
                AND u.delivered_at IS NOT NULL AND u.delivery_date IS NULL"""))


def downgrade():
    op.drop_table("construction_unit_delivery_audits", schema="construction")
    for table in ("construction_unit_sales", "construction_units"):
        op.drop_column(table, "delivery_date", schema="construction")
