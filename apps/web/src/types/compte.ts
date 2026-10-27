export type Platform = 'ig' | 'th' | 'x'
export type CompteWorkflow = 'Onboarding' | 'Warmup' | 'Actif'
export type CompteStatus = 'ok' | 'session' | 'error' | 'suspendu'

export const PLATFORMS: Platform[] = ['ig', 'th', 'x']
export const WORKFLOWS: CompteWorkflow[] = ['Onboarding', 'Warmup', 'Actif']
export const STATUSES: CompteStatus[] = ['ok', 'session', 'error', 'suspendu']

export interface CompteInput {
  handle: string
  persona_id: string | null
  plateforme: Platform
  workflow: CompteWorkflow
  status: CompteStatus
  device_id: string | null
  proxy_id: string | null
  env: Record<string, unknown> | null
  sessions: number
  follows: number
  creds_encrypted?: Record<string, string> | null
}

export interface Compte extends CompteInput {
  id: string
  created_at: string
  updated_at: string
}

export interface CompteFilters {
  persona_id?: string
  plateforme?: Platform
}
