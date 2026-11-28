"""Posting — collections, medias, templates, campagnes, publications, sounds."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Sound(Base):
    """Son IG scrape (trending ou recherche) — persistance locale."""
    __tablename__ = "sounds"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ig_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)  # IG audio ID
    title: Mapped[str] = mapped_column(String(500))
    artist: Mapped[str | None] = mapped_column(String(500))
    cover_url: Mapped[str | None] = mapped_column(Text)
    preview_url: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    use_count: Mapped[int] = mapped_column(Integer, default=0)        # usages sur IG
    ofm_score: Mapped[float] = mapped_column(Float, default=0.0)      # score OFM (veille)
    ig_rank: Mapped[int | None] = mapped_column(Integer)              # rang trending IG
    is_trending: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(50), default="ig_trending")  # ig_trending, ig_search, veille
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class Collection(Base):
    __tablename__ = "collections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150))
    collection_type: Mapped[str] = mapped_column(String(20))  # assembled, variable
    persona_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("personas.id", ondelete="SET NULL")
    )
    plateforme: Mapped[str | None] = mapped_column(String(10))
    post_type: Mapped[str | None] = mapped_column(String(20))  # post, story, reel
    captions: Mapped[list | None] = mapped_column(JSONB, default=list)
    media_ids: Mapped[list | None] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class Media(Base):
    __tablename__ = "medias"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    persona_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("personas.id", ondelete="SET NULL")
    )
    media_type: Mapped[str] = mapped_column(String(10))  # image, video, audio
    url: Mapped[str] = mapped_column(Text)
    thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration: Mapped[int | None] = mapped_column(Integer)  # seconds for video/audio
    tags: Mapped[list | None] = mapped_column(JSONB, default=list)
    folder: Mapped[str | None] = mapped_column(String(100))
    used: Mapped[bool] = mapped_column(Boolean, default=False)  # anti-repeat
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class Template(Base):
    __tablename__ = "templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150))
    persona_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("personas.id", ondelete="SET NULL")
    )
    plateforme: Mapped[str | None] = mapped_column(String(10))
    template_type: Mapped[str] = mapped_column(String(20), default="post")  # post, story
    layers: Mapped[list[dict] | None] = mapped_column(JSONB, default=list)  # calques
    variables: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    collection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("collections.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class StoryTemplate(Base):
    """Template de story 9:16 avec stickers positionnables."""
    __tablename__ = "story_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    persona_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("personas.id", ondelete="SET NULL"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    story_type: Mapped[str] = mapped_column(String(50), default="lifestyle")  # lifestyle, fitness, promo, etc.
    username: Mapped[str] = mapped_column(String(100), default="")
    color: Mapped[str] = mapped_column(String(20), default="#1b1f33")  # fond uni
    media_ids: Mapped[list | None] = mapped_column(JSONB, default=list)  # UUIDs des medias de fond
    bg_idx: Mapped[int] = mapped_column(Integer, default=-1)  # index media actif (-1 = couleur)
    elements: Mapped[list[dict]] = mapped_column(JSONB, default=list)  # stickers [{id,kind,x,y,scale,rot,text,color,...}]
    moments: Mapped[list | None] = mapped_column(JSONB, default=list)  # ["matin","midi",...]
    is_liked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class StoryCollection(Base):
    """Collection de stories : classique (rotation) ou à la une (highlight)."""
    __tablename__ = "story_collections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    persona_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("personas.id", ondelete="SET NULL"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(10))  # story, hl (highlight)
    story_type: Mapped[str | None] = mapped_column(String(50))  # lifestyle, fitness, etc.
    template_ids: Mapped[list | None] = mapped_column(JSONB, default=list)  # UUIDs story_templates
    by_persona: Mapped[dict | None] = mapped_column(JSONB, default=dict)  # {persona_id: {tpls: [...]}}
    highlight_name: Mapped[str | None] = mapped_column(String(200))  # nom du highlight IG
    highlight_icon: Mapped[str | None] = mapped_column(String(50))  # icone
    schedule: Mapped[dict | None] = mapped_column(JSONB, default=dict)  # {days: [...], window: {from, to}}
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class StoryPlanner(Base):
    """Planner de stories — programme la publication automatique."""
    __tablename__ = "story_planners"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    persona_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("personas.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="active")  # active, paused
    rules: Mapped[list[dict]] = mapped_column(JSONB, default=list)  # [{type, freqMode, n, moments, pool}]
    highlight_collections: Mapped[list] = mapped_column(JSONB, default=list)  # [collection_id, ...]
    highlight_config: Mapped[dict] = mapped_column(JSONB, default=dict)  # {coll_id: {mode, n}}
    anti_repetition_days: Mapped[int] = mapped_column(Integer, default=3)
    seed: Mapped[int] = mapped_column(Integer, default=1)
    cycle: Mapped[int] = mapped_column(Integer, default=0)  # incremented on re-shuffle
    loop_cache: Mapped[dict | None] = mapped_column(JSONB)  # cached generated loop
    depth_days: Mapped[int] = mapped_column(Integer, default=0)  # estimated depth
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class StoryType(Base):
    """Type/catégorie de story (Lifestyle, GYM, CTA, Promo, etc.)."""
    __tablename__ = "story_types"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(50), unique=True, index=True)  # ex: lifestyle, gym, cta
    label: Mapped[str] = mapped_column(String(100))  # Nom affiché
    color: Mapped[str] = mapped_column(String(20), default="#4ade80")
    icon: Mapped[str] = mapped_column(String(50), default="sparkle")  # nom Phosphor sans prefixe
    personas: Mapped[list | None] = mapped_column(JSONB, default=list)  # UUIDs des personas associées (vide = toutes)
    position: Mapped[int] = mapped_column(Integer, default=0)  # ordre d'affichage
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class Campagne(Base):
    __tablename__ = "campagnes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150))
    icon: Mapped[str | None] = mapped_column(String(50))
    persona_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("personas.id", ondelete="SET NULL")
    )
    plateforme: Mapped[str | None] = mapped_column(String(10))
    post_type: Mapped[str | None] = mapped_column(String(20))  # post, reel, story, carousel
    collection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("collections.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft, active, paused, done
    accounts: Mapped[list | None] = mapped_column(JSONB, default=list)  # list of compte UUIDs
    scenarios: Mapped[list | None] = mapped_column(JSONB, default=list)  # scenario IDs
    waves: Mapped[list[dict] | None] = mapped_column(JSONB, default=list)  # vagues
    planning: Mapped[dict | None] = mapped_column(JSONB, default=dict)  # {mode, freq, from_h, to_h, days, delay}
    last_posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    post_count: Mapped[int] = mapped_column(Integer, default=0)
    rotation_index: Mapped[int] = mapped_column(Integer, default=0)  # current position in collection rotation
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class Publication(Base):
    __tablename__ = "publications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    compte_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comptes.id", ondelete="CASCADE"), index=True
    )
    campagne_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campagnes.id", ondelete="SET NULL")
    )
    media_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("medias.id", ondelete="SET NULL")
    )
    media_urls: Mapped[list | None] = mapped_column(JSONB, default=list)  # R2 URLs for carousel
    post_type: Mapped[str] = mapped_column(String(20), default="post")  # post, story, reel, carousel
    caption: Mapped[str | None] = mapped_column(Text)
    first_comment: Mapped[str | None] = mapped_column(Text)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="planned")  # planned, published, failed, suspended
    platform_post_id: Mapped[str | None] = mapped_column(String(200))
    stickers: Mapped[dict | None] = mapped_column(JSONB)  # story stickers config
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
