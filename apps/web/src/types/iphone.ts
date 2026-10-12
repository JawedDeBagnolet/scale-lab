export type IPhoneStatus = 'online' | 'offline'

export const IPHONE_STATUSES: IPhoneStatus[] = ['online', 'offline']

export interface Telemetry {
  battery_pct: number | null
  charging: boolean | null
  network_quality: string | null
  data_used_mb: number | null
  current_run: string | null
  current_compte: string | null
  last_run_at: string | null
  offline_since: string | null
}

export interface IPhone {
  id: string
  name: string
  model: string
  ios_version: string
  rack: string | null
  market: string | null
  status: IPhoneStatus
  jailbreak: boolean
  max_comptes: number
  proxy_id: string | null
  telemetry: Telemetry | null
  created_at: string
  updated_at: string
}

export interface IPhoneInput {
  name: string
  model: string
  ios_version: string
  rack: string | null
  market: string | null
  status: IPhoneStatus
  jailbreak: boolean
  max_comptes: number
  proxy_id: string | null
}

export interface IPhoneFilters {
  status?: IPhoneStatus
  market?: string
}
