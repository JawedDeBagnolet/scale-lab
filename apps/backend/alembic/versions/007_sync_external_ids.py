"""007_sync_external_ids — Add external IDs for OC/GMS sync

Revision ID: 007
Revises: 006
Create Date: 2026-10-21

Adds oc_external_id to fans, transactions, scripts
and gms_external_id to tracked_links for sync deduplication.
"""

from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # CRM tables — OC sync
    op.add_column("fans", sa.Column("oc_external_id", sa.String(200), nullable=True))
    op.create_unique_constraint("uq_fans_oc_external_id", "fans", ["oc_external_id"])

    op.add_column("transactions", sa.Column("oc_external_id", sa.String(200), nullable=True))
    op.create_unique_constraint("uq_transactions_oc_external_id", "transactions", ["oc_external_id"])

    op.add_column("scripts", sa.Column("oc_external_id", sa.String(200), nullable=True))
    op.create_unique_constraint("uq_scripts_oc_external_id", "scripts", ["oc_external_id"])

    # Liens table — GMS sync
    op.add_column("tracked_links", sa.Column("gms_external_id", sa.String(200), nullable=True))
    op.create_unique_constraint("uq_tracked_links_gms_external_id", "tracked_links", ["gms_external_id"])


def downgrade() -> None:
    op.drop_constraint("uq_tracked_links_gms_external_id", "tracked_links", type_="unique")
    op.drop_column("tracked_links", "gms_external_id")

    op.drop_constraint("uq_scripts_oc_external_id", "scripts", type_="unique")
    op.drop_column("scripts", "oc_external_id")

    op.drop_constraint("uq_transactions_oc_external_id", "transactions", type_="unique")
    op.drop_column("transactions", "oc_external_id")

    op.drop_constraint("uq_fans_oc_external_id", "fans", type_="unique")
    op.drop_column("fans", "oc_external_id")
