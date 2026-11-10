"""scraper accounts + scrapigo settings

Revision ID: 014
Revises: 013
Create Date: 2024-11-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Scraper accounts table
    op.create_table(
        "scraper_accounts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("platform", sa.String(10), nullable=False),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("password", sa.Text, nullable=True),
        sa.Column("session_data", JSONB, nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("ds_user_id", sa.String(50), nullable=True),
        sa.Column("proxy_country", sa.String(5), nullable=False, server_default="FR"),
        sa.Column("proxy_sticky_id", sa.String(100), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("bytes_used", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("requests_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Scrapigo settings columns
    op.add_column("workspace_settings", sa.Column("scrapigo_api_key", sa.Text, nullable=True))
    op.add_column("workspace_settings", sa.Column("scrapigo_product", sa.String(30), server_default="residential"))
    op.add_column("workspace_settings", sa.Column("scrapigo_country", sa.String(5), server_default="FR"))


def downgrade() -> None:
    op.drop_column("workspace_settings", "scrapigo_country")
    op.drop_column("workspace_settings", "scrapigo_product")
    op.drop_column("workspace_settings", "scrapigo_api_key")
    op.drop_table("scraper_accounts")
