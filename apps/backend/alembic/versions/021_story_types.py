"""Add story_types table.

Revision ID: 021
"""

revision = "021"
down_revision = "020"

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


def upgrade():
    op.create_table(
        "story_types",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("slug", sa.String(50), unique=True, nullable=False, index=True),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("color", sa.String(20), server_default="#4ade80"),
        sa.Column("icon", sa.String(50), server_default="sparkle"),
        sa.Column("personas", JSONB, server_default="[]"),
        sa.Column("position", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Seed default story types
    op.execute("""
        INSERT INTO story_types (slug, label, color, icon, personas, position) VALUES
        ('lifestyle', 'Lifestyle', '#2dd4a8', 'sun', '[]', 0),
        ('gym', 'GYM', '#4ade80', 'barbell', '[]', 1),
        ('cta', 'CTA', '#f5b04c', 'megaphone-simple', '[]', 2),
        ('promo', 'Promo', '#f472b6', 'tag', '[]', 3),
        ('repost', 'Repost', '#8db4fd', 'repeat', '[]', 4),
        ('question', 'Question', '#a5a0f5', 'chat-circle-dots', '[]', 5),
        ('bts', 'Coulisses', '#fb923c', 'camera', '[]', 6)
    """)


def downgrade():
    op.drop_table("story_types")
