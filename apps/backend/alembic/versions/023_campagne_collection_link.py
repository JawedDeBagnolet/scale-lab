"""Add collection_id, post_type, accounts, tracking fields to campagnes.

Revision ID: 023
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "023"
down_revision = "022"


def upgrade():
    op.add_column("campagnes", sa.Column("post_type", sa.String(20)))
    op.add_column("campagnes", sa.Column("collection_id", UUID(as_uuid=True),
                  sa.ForeignKey("collections.id", ondelete="SET NULL")))
    op.add_column("campagnes", sa.Column("accounts", JSONB, server_default="[]"))
    op.add_column("campagnes", sa.Column("last_posted_at", sa.DateTime(timezone=True)))
    op.add_column("campagnes", sa.Column("post_count", sa.Integer, server_default="0"))
    op.add_column("campagnes", sa.Column("rotation_index", sa.Integer, server_default="0"))


def downgrade():
    op.drop_column("campagnes", "rotation_index")
    op.drop_column("campagnes", "post_count")
    op.drop_column("campagnes", "last_posted_at")
    op.drop_column("campagnes", "accounts")
    op.drop_column("campagnes", "collection_id")
    op.drop_column("campagnes", "post_type")
