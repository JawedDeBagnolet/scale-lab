from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DailyStatBase(BaseModel):
    compte_id: UUID
    date: date
    followers: int = 0
    gained: int = 0
    lost: int = 0
    reach: int = 0
    impressions: int = 0
    engagements: int = 0
    profile_visits: int = 0
    bio_clicks: int = 0
    story_views: int = 0
    posts_published: int = 0
    stories_published: int = 0
    availability: float = Field(default=1.0, ge=0.0, le=1.0)


class DailyStatCreate(DailyStatBase):
    pass


class DailyStatOut(DailyStatBase):
    id: UUID
    created_at: datetime

    # Computed fields
    net_gain: int | None = None
    engagement_rate: float | None = None
    avg_impressions_per_post: float | None = None
    conversion_rate: float | None = None

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, stat: object) -> "DailyStatOut":
        """Build output with computed fields from a DailyStat model instance."""
        out = cls.model_validate(stat)
        out.net_gain = out.gained - out.lost
        out.engagement_rate = (out.engagements / out.followers * 100) if out.followers > 0 else 0.0
        out.avg_impressions_per_post = (
            out.impressions / out.posts_published if out.posts_published > 0 else None
        )
        out.conversion_rate = (
            out.bio_clicks / out.profile_visits * 100 if out.profile_visits > 0 else None
        )
        return out


class StatsOverview(BaseModel):
    total_followers: int
    avg_engagement_rate: float
    total_reach_30d: int
    best_day: date | None = None


class StatFilters(BaseModel):
    compte_id: UUID
    date_from: date | None = None
    date_to: date | None = None


class DailyStatBulkCreate(BaseModel):
    """Import en masse de stats quotidiennes."""

    stats: list[DailyStatCreate]
