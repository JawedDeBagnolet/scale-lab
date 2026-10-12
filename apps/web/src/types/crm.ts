export type TransactionType = 'sub' | 'ppv' | 'tip'

export interface FanInput {
  pseudo: string
  creator_id: string
  compte_id: string | null
  platform_origin: string
  joined_at: string
  total_spent: number
  last_activity: string | null
  notes: string | null
}

export interface Fan extends FanInput {
  id: string
  created_at: string
  updated_at: string
}

export interface FanFilters {
  creator_id?: string
  platform_origin?: string
}

export interface TransactionInput {
  fan_id: string
  creator_id: string
  transaction_type: TransactionType
  amount: number
  script_id: string | null
  compte_id: string | null
  timestamp: string
}

export interface Transaction extends TransactionInput {
  id: string
  created_at: string
}

export interface TransactionFilters {
  fan_id?: string
  creator_id?: string
  type?: TransactionType
  date_from?: string
  date_to?: string
}

export interface ScriptInput {
  script_group_id: string | null
  folder: string | null
  active: boolean
  priority: boolean
  steps: Record<string, unknown>[] | null
  stats: Record<string, unknown> | null
}

export interface Script extends ScriptInput {
  id: string
  created_at: string
  updated_at: string
}

export interface ScriptFilters {
  active?: boolean
  folder?: string
}

export interface CrmOverview {
  total_fans: number
  total_revenue: number
  avg_ltv: number
  top_script: string | null
}
