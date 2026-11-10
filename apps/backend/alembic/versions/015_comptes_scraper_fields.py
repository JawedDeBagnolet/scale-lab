"""Add scraper fields to comptes + drop scraper_accounts table.

Revision ID: 015
Revises: 014
"""

from alembic import op
import sqlalchemy as sa

revision = "015"
down_revision = "014"


def upgrade():
    # Add scraper columns to comptes
    op.add_column("comptes", sa.Column("is_scraper", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("comptes", sa.Column("session_data", sa.JSON(), nullable=True))
    op.add_column("comptes", sa.Column("scraper_bytes_used", sa.BigInteger(), server_default="0", nullable=False))
    op.add_column("comptes", sa.Column("scraper_requests_count", sa.Integer(), server_default="0", nullable=False))

    # Drop scraper_accounts table (data migrated to comptes)
    op.drop_table("scraper_accounts")


def downgrade():
    op.drop_column("comptes", "scraper_requests_count")
    op.drop_column("comptes", "scraper_bytes_used")
    op.drop_column("comptes", "session_data")
    op.drop_column("comptes", "is_scraper")

    # Recreate scraper_accounts (simplified — no data restore)
    op.create_table(
        "scraper_accounts",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("platform", sa.String(10), nullable=False),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("password", sa.Text(), nullable=True),
        sa.Column("session_data", sa.JSON(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("ds_user_id", sa.String(50), nullable=True),
        sa.Column("proxy_country", sa.String(5), server_default="FR"),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("bytes_used", sa.BigInteger(), server_default="0"),
        sa.Column("requests_count", sa.Integer(), server_default="0"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
