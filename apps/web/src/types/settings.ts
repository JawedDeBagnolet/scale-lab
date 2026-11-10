export interface IntegrationStatus {
  connected: boolean
  last_sync: string | null
  key_tail: string | null
}

export interface WorkspaceSettings {
  name: string
  currency: string
  timezone: string
  oc: IntegrationStatus
  gms: IntegrationStatus
  tg: IntegrationStatus
  scrapigo: IntegrationStatus
  env_providers: Record<string, unknown> | null
  notifications: NotificationsConfig | null
  updated_at: string
}

export interface WorkspaceUpdate {
  name?: string
  currency?: string
  timezone?: string
}

export interface IntegrationUpdate {
  api_key?: string
  bot_token?: string
  chat_id?: string
  test?: boolean
}

export interface NotificationsConfig {
  domain_full?: boolean
  oc_balance_low?: boolean
  link_unavailable?: boolean
}

// Scraper accounts
export interface ScraperAccount {
  id: string
  platform: string
  username: string
  has_password: boolean
  ds_user_id: string | null
  user_agent: string | null
  has_session: boolean
  proxy_country: string
  status: string
  last_error: string | null
  bytes_used: number
  requests_count: number
  last_used_at: string | null
  created_at: string
  updated_at: string
}

export interface ScraperAccountCreate {
  platform: string
  username: string
  password?: string
  proxy_country?: string
}
