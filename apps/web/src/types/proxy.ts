export type ProxyStatus = 'online' | 'offline' | 'error'
export type ProxyType = '4G' | '5G'

export const PROXY_STATUSES: ProxyStatus[] = ['online', 'offline', 'error']
export const PROXY_TYPES: ProxyType[] = ['4G', '5G']

export interface ProxyInput {
  pool: string
  type: ProxyType
  iphone_id: string | null
  ip: string
  country: string
  latency_ms: number | null
  status: ProxyStatus
  blacklists: string[]
  availability_7d: number
}

export interface Proxy extends ProxyInput {
  id: string
  created_at: string
  updated_at: string
}

export interface ProxyFilters {
  pool?: string
  status?: ProxyStatus
  country?: string
}
