export interface DailyStat {
  id: string
  compte_id: string
  date: string
  followers: number
  gained: number
  lost: number
  reach: number
  impressions: number
  engagements: number
  profile_visits: number
  bio_clicks: number
  story_views: number
  posts_published: number
  stories_published: number
  availability: number
  created_at: string

  // Computed fields
  net_gain: number | null
  engagement_rate: number | null
  avg_impressions_per_post: number | null
  conversion_rate: number | null
}

export interface StatsOverview {
  total_followers: number
  avg_engagement_rate: number
  total_reach_30d: number
  best_day: string | null
}

export interface StatFilters {
  compte_id: string
  date_from?: string
  date_to?: string
}
