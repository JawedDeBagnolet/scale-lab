"""Add thumbnail_url to medias"""
from alembic import op
import sqlalchemy as sa

revision = "018"
down_revision = "017"


def upgrade():
    op.add_column("medias", sa.Column("thumbnail_url", sa.Text, nullable=True))


def downgrade():
    op.drop_column("medias", "thumbnail_url")
