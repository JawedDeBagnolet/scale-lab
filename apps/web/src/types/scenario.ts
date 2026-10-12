export const SCENARIO_ORIGINS = ['spontane', 'login', 'creation'] as const
export type ScenarioOrigin = (typeof SCENARIO_ORIGINS)[number]

export const RUN_STATUSES = ['pending', 'running', 'paused', 'done', 'error'] as const
export type RunStatus = (typeof RUN_STATUSES)[number]

export interface ScenarioStep {
  action: string
  preset_id?: string
  delay_min?: number
  delay_max?: number
  config?: Record<string, unknown>
}

export interface TimeRange {
  start: string
  end: string
}

export interface Scenario {
  id: string
  name: string
  origin: ScenarioOrigin
  couple: string | null
  plateforme: string | null
  slots: Record<string, unknown>[]
  steps: ScenarioStep[]
  loop: boolean
  active: boolean
  description: string | null
  created_at: string
  updated_at: string
}

export interface ScenarioInput {
  name: string
  origin: ScenarioOrigin
  couple?: string | null
  plateforme?: string | null
  slots?: Record<string, unknown>[]
  steps?: ScenarioStep[]
  loop?: boolean
  active?: boolean
  description?: string | null
}

export interface ScenarioFilters {
  origin?: string
  plateforme?: string
  active?: boolean
}

export interface Run {
  id: string
  scenario_id: string
  comptes: string[]
  current_step: number
  status: RunStatus
  blocked_accounts: string[]
  journal: Record<string, unknown>[]
  started_at: string | null
  finished_at: string | null
  created_at: string
}

export interface RunInput {
  scenario_id: string
  comptes?: string[]
  current_step?: number
  status?: RunStatus
}

export interface RunFilters {
  scenario_id?: string
  status?: string
}

export interface PlageHoraire {
  id: string
  name: string
  days: number[]
  ranges: TimeRange[]
  created_at: string
  updated_at: string
}

export interface PlageHoraireInput {
  name: string
  days?: number[]
  ranges?: TimeRange[]
}

export interface ScenariosOverview {
  total_scenarios: number
  active_scenarios: number
  total_runs: number
  running_now: number
  total_plages: number
}
