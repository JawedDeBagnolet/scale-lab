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
