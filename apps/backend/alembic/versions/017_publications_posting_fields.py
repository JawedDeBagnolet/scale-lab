"""Add post_type, media_urls, first_comment, stickers to publications"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "017"
down_revision = "016"


def upgrade():
    op.add_column("publications", sa.Column("post_type", sa.String(20), server_default="post", nullable=False))
    op.add_column("publications", sa.Column("media_urls", JSONB, nullable=True))
    op.add_column("publications", sa.Column("first_comment", sa.Text, nullable=True))
    op.add_column("publications", sa.Column("stickers", JSONB, nullable=True))


def downgrade():
    op.drop_column("publications", "stickers")
    op.drop_column("publications", "first_comment")
    op.drop_column("publications", "media_urls")
    op.drop_column("publications", "post_type")
