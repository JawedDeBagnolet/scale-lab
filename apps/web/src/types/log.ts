export type EventLevel = 'info' | 'warning' | 'error' | 'critical'
export type IncidentStatus = 'open' | 'ack' | 'resolved'

export const EVENT_LEVELS: EventLevel[] = ['info', 'warning', 'error', 'critical']
export const INCIDENT_STATUSES: IncidentStatus[] = ['open', 'ack', 'resolved']

export const LEVEL_COLORS: Record<EventLevel, string> = {
  info: '#4b7bf5',
  warning: '#f59e0b',
  error: '#ef4444',
  critical: '#dc2626',
}

export const INCIDENT_STATUS_COLORS: Record<IncidentStatus, string> = {
  open: '#ef4444',
  ack: '#f59e0b',
  resolved: '#22c55e',
}

export const INCIDENT_STATUS_LABELS: Record<IncidentStatus, string> = {
  open: 'Ouvert',
  ack: 'Pris en charge',
  resolved: 'Resolu',
}

export interface LogEvent {
  id: string
  timestamp: string
  module: string
  event_type: string
  level: EventLevel
  target: string | null
  cause: string | null
  code: string | null
  message: string
  meta: Record<string, unknown> | null
}

export interface Incident {
  id: string
  module: string
  event_type: string
  target: string | null
  status: IncidentStatus
  event_count: number
  first_seen: string
  last_seen: string
  solutions: unknown[] | null
  related_events: unknown[] | null
  meta: Record<string, unknown> | null
}

export interface AlertRule {
  id: string
  module: string
  event_type: string
  threshold_errors: number
  threshold_actions: number
  tg_enabled: boolean
  created_at: string
}

export interface LogStats {
  total_events: number
  errors_24h: number
  open_incidents: number
  modules: Record<string, number>
}

export interface AlertRuleCreate {
  module: string
  event_type: string
  threshold_errors?: number
  threshold_actions?: number
  tg_enabled?: boolean
}

export interface EventFilters {
  module?: string
  level?: EventLevel
  target?: string
  limit?: number
  offset?: number
}
