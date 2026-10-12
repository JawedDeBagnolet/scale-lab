import type { Platform } from './compte'

export type TargetStatus = 'ok' | 'prive' | 'renomme' | 'banni'
export type TargetSource = 'manual' | 'veille' | 'import'

export const TARGET_STATUSES: TargetStatus[] = ['ok', 'prive', 'renomme', 'banni']
export const TARGET_SOURCES: TargetSource[] = ['manual', 'veille', 'import']

export interface TargetInput {
  handle: string
  plateforme: Platform
  market: string | null
  niche_id: number | null
  status: TargetStatus
  source: TargetSource
}

export interface Target extends TargetInput {
  id: string
  created_at: string
  updated_at: string
}

export interface TargetFilters {
  plateforme?: Platform
  market?: string
  niche_id?: number
  status?: TargetStatus
}
