"""Add profile_data and profile_config to comptes"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "016"
down_revision = "015"

def upgrade():
    op.add_column("comptes", sa.Column("profile_data", JSONB, nullable=True))
    op.add_column("comptes", sa.Column("profile_config", JSONB, nullable=True))

def downgrade():
    op.drop_column("comptes", "profile_config")
    op.drop_column("comptes", "profile_data")
