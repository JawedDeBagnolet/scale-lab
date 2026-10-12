import type { Platform } from './compte'

// --- VeilleSource ----------------------------------------------------------

export interface VeilleSourceInput {
  handle: string
  plateforme: Platform
  niche_id: number | null
  active: boolean
}

export interface VeilleSource extends VeilleSourceInput {
  id: string
  last_checked: string | null
  created_at: string
  updated_at: string
}

export interface VeilleSourceFilters {
  plateforme?: Platform
  niche_id?: number
  active?: boolean
}

// --- Inspiration -----------------------------------------------------------

export type MediaType = 'image' | 'video' | 'reel'
export type InspirationStatus = 'new' | 'reviewed' | 'used' | 'dismissed'

export const MEDIA_TYPES: MediaType[] = ['image', 'video', 'reel']
export const INSPIRATION_STATUSES: InspirationStatus[] = ['new', 'reviewed', 'used', 'dismissed']

export interface Inspiration {
  id: string
  source_id: string
  url: string
  media_type: MediaType
  caption: string | null
  engagement: number
  saved_at: string
  status: InspirationStatus
  created_at: string
}

export interface InspirationFilters {
  source_id?: string
  status?: InspirationStatus
  media_type?: MediaType
}

// --- Favorite --------------------------------------------------------------

export interface FavoriteInput {
  inspiration_id: string
  album_id: string | null
  notes: string | null
}

export interface Favorite extends FavoriteInput {
  id: string
  created_at: string
}

export interface FavoriteFilters {
  album_id?: string
}

// --- Snipe -----------------------------------------------------------------

export type SnipePriority = 'low' | 'medium' | 'high'
export type SnipeStatus = 'pending' | 'in_progress' | 'done' | 'cancelled'

export const SNIPE_PRIORITIES: SnipePriority[] = ['low', 'medium', 'high']
export const SNIPE_STATUSES: SnipeStatus[] = ['pending', 'in_progress', 'done', 'cancelled']

export interface SnipeInput {
  inspiration_id: string
  target_persona_id: string | null
  priority: SnipePriority
  status: SnipeStatus
  due_date: string | null
}

export interface Snipe extends SnipeInput {
  id: string
  created_at: string
  updated_at: string
}

export interface SnipeFilters {
  status?: SnipeStatus
  priority?: SnipePriority
  persona_id?: string
}

// --- Album -----------------------------------------------------------------

export interface AlbumInput {
  name: string
  description: string | null
  persona_id: string | null
}

export interface Album extends AlbumInput {
  id: string
  created_at: string
  updated_at: string
}

export interface AlbumFilters {
  persona_id?: string
}

// --- Overview --------------------------------------------------------------

export interface VeilleOverview {
  total_sources: number
  new_inspirations: number
  pending_snipes: number
  total_albums: number
}
