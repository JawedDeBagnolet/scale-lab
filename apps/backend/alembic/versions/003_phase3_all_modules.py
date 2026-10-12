"""003_phase3_all_modules

Revision ID: 003
Revises: 002
Create Date: 2026-10-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Proxies ------------------------------------------------------------------
    op.create_table(
        "proxies",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("pool", sa.String(20), nullable=False),
        sa.Column("type", sa.String(10), nullable=False),
        sa.Column("iphone_id", sa.UUID(), nullable=True),
        sa.Column("ip", sa.String(45), nullable=False),
        sa.Column("country", sa.String(5), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), server_default="online", nullable=False),
        sa.Column("blacklists", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("availability_7d", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- iPhones ------------------------------------------------------------------
    op.create_table(
        "iphones",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("model", sa.String(50), nullable=False),
        sa.Column("ios_version", sa.String(20), nullable=False),
        sa.Column("rack", sa.String(20), nullable=True),
        sa.Column("market", sa.String(10), nullable=True),
        sa.Column("status", sa.String(20), server_default="offline", nullable=False),
        sa.Column("jailbreak", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("max_comptes", sa.Integer(), server_default="3", nullable=False),
        sa.Column("proxy_id", sa.UUID(), nullable=True),
        sa.Column("telemetry", postgresql.JSONB(), server_default="{}", nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- Daily Stats --------------------------------------------------------------
    op.create_table(
        "daily_stats",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("compte_id", sa.UUID(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("followers", sa.Integer(), server_default="0", nullable=False),
        sa.Column("gained", sa.Integer(), server_default="0", nullable=False),
        sa.Column("lost", sa.Integer(), server_default="0", nullable=False),
        sa.Column("reach", sa.Integer(), server_default="0", nullable=False),
        sa.Column("impressions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("engagements", sa.Integer(), server_default="0", nullable=False),
        sa.Column("profile_visits", sa.Integer(), server_default="0", nullable=False),
        sa.Column("bio_clicks", sa.Integer(), server_default="0", nullable=False),
        sa.Column("story_views", sa.Integer(), server_default="0", nullable=False),
        sa.Column("posts_published", sa.Integer(), server_default="0", nullable=False),
        sa.Column("stories_published", sa.Integer(), server_default="0", nullable=False),
        sa.Column("availability", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_daily_stats_compte_id", "daily_stats", ["compte_id"])
    op.create_index("ix_daily_stats_date", "daily_stats", ["date"])

    # --- Domains ------------------------------------------------------------------
    op.create_table(
        "domains",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("host", sa.String(100), nullable=False, unique=True),
        sa.Column("max_active_links", sa.Integer(), server_default="500", nullable=False),
        sa.Column("alert_threshold", sa.Integer(), server_default="450", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- Tracked Links ------------------------------------------------------------
    op.create_table(
        "tracked_links",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("domain_id", sa.UUID(), sa.ForeignKey("domains.id"), nullable=True),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("link_type", sa.String(10), server_default="direct", nullable=False),
        sa.Column("destination", sa.Text(), nullable=False),
        sa.Column("plateforme", sa.String(10), nullable=False),
        sa.Column("persona_id", sa.UUID(), nullable=True),
        sa.Column("compte_id", sa.UUID(), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("group_name", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- Click Events -------------------------------------------------------------
    op.create_table(
        "click_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("link_id", sa.UUID(), sa.ForeignKey("tracked_links.id"), nullable=False),
        sa.Column("clicked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("country", sa.String(5), nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("device", sa.String(50), nullable=False),
        sa.Column("browser", sa.String(50), nullable=False),
        sa.Column("referrer", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- Veille Sources -----------------------------------------------------------
    op.create_table(
        "veille_sources",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("handle", sa.String(100), nullable=False),
        sa.Column("plateforme", sa.String(10), nullable=False),
        sa.Column("niche_id", sa.Integer(), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("last_checked", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- Inspirations -------------------------------------------------------------
    op.create_table(
        "inspirations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("media_type", sa.String(20), nullable=False),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("engagement", sa.Integer(), server_default="0", nullable=False),
        sa.Column("saved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), server_default="new", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_inspirations_source_id", "inspirations", ["source_id"])

    # --- Favorites ----------------------------------------------------------------
    op.create_table(
        "favorites",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("inspiration_id", sa.UUID(), nullable=False),
        sa.Column("album_id", sa.UUID(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_favorites_inspiration_id", "favorites", ["inspiration_id"])

    # --- Snipes -------------------------------------------------------------------
    op.create_table(
        "snipes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("inspiration_id", sa.UUID(), nullable=False),
        sa.Column("target_persona_id", sa.UUID(), nullable=True),
        sa.Column("priority", sa.String(10), server_default="medium", nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_snipes_inspiration_id", "snipes", ["inspiration_id"])

    # --- Albums -------------------------------------------------------------------
    op.create_table(
        "albums",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("persona_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- Fans (CRM) ---------------------------------------------------------------
    op.create_table(
        "fans",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("pseudo", sa.String(100), nullable=False),
        sa.Column("creator_id", sa.UUID(), nullable=False),
        sa.Column("compte_id", sa.UUID(), nullable=True),
        sa.Column("platform_origin", sa.String(10), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_spent", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_activity", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- Transactions (CRM) -------------------------------------------------------
    op.create_table(
        "transactions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("fan_id", sa.UUID(), nullable=False),
        sa.Column("creator_id", sa.UUID(), nullable=False),
        sa.Column("transaction_type", sa.String(10), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("script_id", sa.UUID(), nullable=True),
        sa.Column("compte_id", sa.UUID(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- Scripts (CRM) ------------------------------------------------------------
    op.create_table(
        "scripts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("script_group_id", sa.UUID(), nullable=True),
        sa.Column("folder", sa.String(100), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("priority", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("steps", postgresql.JSONB(), server_default="[]", nullable=True),
        sa.Column("stats", postgresql.JSONB(), server_default="{}", nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- Scenarios ----------------------------------------------------------------
    op.create_table(
        "scenarios",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("origin", sa.String(20), nullable=False),
        sa.Column("couple", sa.String(100), nullable=True),
        sa.Column("plateforme", sa.String(10), nullable=True),
        sa.Column("slots", postgresql.JSONB(), server_default="[]", nullable=True),
        sa.Column("steps", postgresql.JSONB(), server_default="[]", nullable=True),
        sa.Column("loop", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- Runs ---------------------------------------------------------------------
    op.create_table(
        "runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("scenario_id", sa.UUID(), nullable=False),
        sa.Column("comptes", postgresql.JSONB(), server_default="[]", nullable=True),
        sa.Column("current_step", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("blocked_accounts", postgresql.JSONB(), server_default="[]", nullable=True),
        sa.Column("journal", postgresql.JSONB(), server_default="[]", nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_runs_scenario_id", "runs", ["scenario_id"])

    # --- Plages Horaires ----------------------------------------------------------
    op.create_table(
        "plages_horaires",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("days", postgresql.JSONB(), server_default="[]", nullable=True),
        sa.Column("ranges", postgresql.JSONB(), server_default="[]", nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- Collections (Posting) ----------------------------------------------------
    op.create_table(
        "collections",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("collection_type", sa.String(20), nullable=False),
        sa.Column("persona_id", sa.UUID(), nullable=True),
        sa.Column("plateforme", sa.String(10), nullable=True),
        sa.Column("post_type", sa.String(20), nullable=True),
        sa.Column("captions", postgresql.JSONB(), server_default="[]", nullable=True),
        sa.Column("media_ids", postgresql.JSONB(), server_default="[]", nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- Medias (Posting) ---------------------------------------------------------
    op.create_table(
        "medias",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("persona_id", sa.UUID(), nullable=True),
        sa.Column("media_type", sa.String(10), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("duration", sa.Integer(), nullable=True),
        sa.Column("tags", postgresql.JSONB(), server_default="[]", nullable=True),
        sa.Column("folder", sa.String(100), nullable=True),
        sa.Column("used", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- Templates (Posting) ------------------------------------------------------
    op.create_table(
        "templates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("persona_id", sa.UUID(), nullable=True),
        sa.Column("plateforme", sa.String(10), nullable=True),
        sa.Column("template_type", sa.String(20), server_default="post", nullable=False),
        sa.Column("layers", postgresql.JSONB(), server_default="[]", nullable=True),
        sa.Column("variables", postgresql.JSONB(), server_default="{}", nullable=True),
        sa.Column("collection_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- Campagnes (Posting) ------------------------------------------------------
    op.create_table(
        "campagnes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("icon", sa.String(50), nullable=True),
        sa.Column("persona_id", sa.UUID(), nullable=True),
        sa.Column("plateforme", sa.String(10), nullable=True),
        sa.Column("status", sa.String(20), server_default="draft", nullable=False),
        sa.Column("scenarios", postgresql.JSONB(), server_default="[]", nullable=True),
        sa.Column("waves", postgresql.JSONB(), server_default="[]", nullable=True),
        sa.Column("planning", postgresql.JSONB(), server_default="{}", nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- Publications (Posting) ---------------------------------------------------
    op.create_table(
        "publications",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("compte_id", sa.UUID(), nullable=False),
        sa.Column("campagne_id", sa.UUID(), nullable=True),
        sa.Column("media_id", sa.UUID(), nullable=True),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), server_default="planned", nullable=False),
        sa.Column("platform_post_id", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_publications_compte_id", "publications", ["compte_id"])


def downgrade() -> None:
    op.drop_table("publications")
    op.drop_table("campagnes")
    op.drop_table("templates")
    op.drop_table("medias")
    op.drop_table("collections")
    op.drop_table("plages_horaires")
    op.drop_table("runs")
    op.drop_table("scenarios")
    op.drop_table("scripts")
    op.drop_table("transactions")
    op.drop_table("fans")
    op.drop_table("albums")
    op.drop_table("snipes")
    op.drop_table("favorites")
    op.drop_table("inspirations")
    op.drop_table("veille_sources")
    op.drop_table("click_events")
    op.drop_table("tracked_links")
    op.drop_table("domains")
    op.drop_table("daily_stats")
    op.drop_table("iphones")
    op.drop_table("proxies")
