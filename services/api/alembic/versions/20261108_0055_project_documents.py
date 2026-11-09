from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "20261108_0055"
down_revision = "20261108_0054"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "construction_project_documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid()),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("identity", sa.String(160), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("snapshot", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["construction.construction_projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("company_id", "identity", name="uq_construction_project_document_identity"),
        schema="construction",
    )
    op.create_index("ix_construction_project_documents_project_id", "construction_project_documents", ["project_id"],
                    schema="construction")


def downgrade():
    op.drop_table("construction_project_documents", schema="construction")
