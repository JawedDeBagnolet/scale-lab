"""Add sounds table for IG music persistence.

Revision ID: 019
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "sounds",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("ig_id", sa.String(100), unique=True, index=True, nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("artist", sa.String(500)),
        sa.Column("cover_url", sa.Text),
        sa.Column("preview_url", sa.Text),
        sa.Column("duration_ms", sa.Integer),
        sa.Column("use_count", sa.Integer, server_default="0"),
        sa.Column("ofm_score", sa.Float, server_default="0"),
        sa.Column("ig_rank", sa.Integer),
        sa.Column("is_trending", sa.Boolean, server_default="false"),
        sa.Column("source", sa.String(50), server_default="'ig_trending'"),
        sa.Column("scraped_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("sounds")
