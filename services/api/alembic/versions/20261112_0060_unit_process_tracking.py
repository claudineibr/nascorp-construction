from alembic import op
import sqlalchemy as sa

revision = "20261112_0060"
down_revision = "20261111_0059"
branch_labels = None
depends_on = None


def upgrade():
    for name, kind in (
        ("correspondent", sa.String(120)), ("correspondent_date", sa.Date()),
        ("client_situation", sa.String(40)), ("client_situation_date", sa.Date()),
        ("process_status", sa.String(40)), ("process_status_date", sa.Date()),
    ):
        op.add_column("construction_units", sa.Column(name, kind, nullable=True), schema="construction")


def downgrade():
    for name in ("process_status_date", "process_status", "client_situation_date", "client_situation", "correspondent_date", "correspondent"):
        op.drop_column("construction_units", name, schema="construction")
