import type { Platform } from './compte'

export type LinkType = 'direct' | 'landing'

export const LINK_TYPES: LinkType[] = ['direct', 'landing']

export interface TrackedLink {
  id: string
  domain_id: string | null
  slug: string
  link_type: LinkType
  destination: string
  plateforme: Platform
  persona_id: string | null
  compte_id: string | null
  active: boolean
  group_name: string | null
  created_at: string
  updated_at: string
}

export interface LinkInput {
  domain_id: string | null
  slug: string
  link_type: LinkType
  destination: string
  plateforme: Platform
  persona_id: string | null
  compte_id: string | null
  active: boolean
  group_name: string | null
}

export interface LinkFilters {
  domain_id?: string
  plateforme?: Platform
  active?: boolean
}

export interface Domain {
  id: string
  host: string
  max_active_links: number
  alert_threshold: number
  created_at: string
  updated_at: string
}

export interface DomainInput {
  host: string
  max_active_links: number
  alert_threshold: number
}

export interface ClickEvent {
  id: string
  link_id: string
  clicked_at: string
  country: string
  city: string
  device: string
  browser: string
  referrer: string | null
}

export interface LinkStats {
  clicks_total: number
  clicks_7d: number
  clicks_today: number
  unique_countries: number
}
