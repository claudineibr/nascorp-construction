from alembic import op
import sqlalchemy as sa

revision = '20261105_0052'
down_revision = '20261105_0051'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('construction_units', sa.Column('original_description', sa.Text(), nullable=True), schema='construction')


def downgrade():
    op.drop_column('construction_units', 'original_description', schema='construction')
