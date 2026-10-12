import type { Platform } from './compte'

export type SessionType = 'browse' | 'engage' | 'publish' | 'warmup'
export const SESSION_TYPES: SessionType[] = ['browse', 'engage', 'publish', 'warmup']

export const SESSION_TYPE_LABELS: Record<SessionType, string> = {
  browse: 'Browse',
  engage: 'Engage',
  publish: 'Publish',
  warmup: 'Warmup',
}

export interface PresetConfig {
  probabilities?: Record<string, number>
  pauses?: { min: number; max: number }
  durations?: { min: number; max: number }
  [key: string]: unknown
}

export interface PresetInput {
  name: string
  plateforme: Platform
  session_type: SessionType
  description: string | null
  is_default: boolean
  config: PresetConfig
}

export interface Preset extends PresetInput {
  id: string
  created_at: string
  updated_at: string
}

export interface PresetFilters {
  plateforme?: Platform
  session_type?: SessionType
}
