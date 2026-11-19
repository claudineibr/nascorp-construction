from alembic import op

revision = "20261118_0062"
down_revision = "20261116_0061"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(op.f("ck_construction_subcontracts_ck_subcontract_pricing_mode"), "construction_subcontracts", schema="construction")
    op.create_check_constraint("ck_subcontract_pricing_mode", "construction_subcontracts",
        "pricing_mode IN ('ITEMIZED','GLOBAL','MEASURED')", schema="construction")
    op.drop_constraint(op.f("ck_construction_subcontracts_ck_subcontract_global_amount"), "construction_subcontracts", schema="construction")
    op.create_check_constraint("ck_subcontract_global_amount", "construction_subcontracts",
        "pricing_mode NOT IN ('GLOBAL','MEASURED') OR global_amount > 0", schema="construction")


def downgrade():
    op.drop_constraint(op.f("ck_construction_subcontracts_ck_subcontract_global_amount"), "construction_subcontracts", schema="construction")
    op.create_check_constraint("ck_subcontract_global_amount", "construction_subcontracts",
        "pricing_mode <> 'GLOBAL' OR global_amount > 0", schema="construction")
    op.drop_constraint(op.f("ck_construction_subcontracts_ck_subcontract_pricing_mode"), "construction_subcontracts", schema="construction")
    op.create_check_constraint("ck_subcontract_pricing_mode", "construction_subcontracts",
        "pricing_mode IN ('ITEMIZED','GLOBAL')", schema="construction")
