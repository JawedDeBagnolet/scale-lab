import { useEffect, useRef, useState } from 'react'
import type { EventLevel, LogEvent } from '../types/log'

const WS_BASE = (import.meta.env.VITE_API_BASE || 'https://api.scalelab.win')
  .replace(/^http/, 'ws')

/**
 * Normalize any WS message into a LogEvent for the live tab.
 * - type:"log_event" → already has the right shape
 * - type:"run_progress" → synthesize a LogEvent from run data
 * - type:"iphone_status" → synthesize a LogEvent from iPhone data
 * - anything else → try to use as-is
 */
function toLogEvent(data: Record<string, unknown>): LogEvent | null {
  const type = data.type as string | undefined

  if (type === 'pong') return null

  if (type === 'log_event') {
    return {
      id: (data.id as string) ?? crypto.randomUUID(),
      timestamp: (data.timestamp as string) ?? new Date().toISOString(),
      module: (data.module as string) ?? '',
      event_type: (data.event_type as string) ?? '',
      level: (data.level as EventLevel) ?? 'info',
      target: (data.target as string) ?? null,
      cause: (data.cause as string) ?? null,
      code: (data.code as string) ?? null,
      message: (data.message as string) ?? '',
      meta: (data.meta as Record<string, unknown>) ?? null,
    }
  }

  if (type === 'run_progress') {
    const status = data.status as string
    const level: EventLevel = status === 'error' ? 'error' : 'info'
    return {
      id: crypto.randomUUID(),
      timestamp: (data.ts as string) ?? new Date().toISOString(),
      module: 'scenarios',
      event_type: `run.${status}`,
      level,
      target: (data.run_id as string) ?? null,
      cause: null,
      code: null,
      message: `Run ${data.run_id} — step ${data.current_step ?? '?'} — ${status}`,
      meta: { run_id: data.run_id, current_step: data.current_step },
    }
  }

  if (type === 'iphone_status') {
    const status = data.status as string
    const level: EventLevel = status === 'offline' ? 'warning' : 'info'
    return {
      id: crypto.randomUUID(),
      timestamp: (data.ts as string) ?? new Date().toISOString(),
      module: 'iphones',
      event_type: `device.${status}`,
      level,
      target: (data.name as string) ?? null,
      cause: null,
      code: null,
      message: `iPhone ${data.name ?? '?'} — ${status}`,
      meta: { iphone_id: data.iphone_id },
    }
  }

  // Fallback: try to use as a raw LogEvent (backward compat)
  if (data.module && data.message) {
    return {
      id: (data.id as string) ?? crypto.randomUUID(),
      timestamp: (data.timestamp as string) ?? new Date().toISOString(),
      module: data.module as string,
      event_type: (data.event_type as string) ?? '',
      level: (data.level as EventLevel) ?? 'info',
      target: (data.target as string) ?? null,
      cause: (data.cause as string) ?? null,
      code: (data.code as string) ?? null,
      message: data.message as string,
      meta: (data.meta as Record<string, unknown>) ?? null,
    }
  }

  return null
}

/**
 * Live WebSocket hook for log events.
 * Maintains a rolling buffer of the last `maxEvents` events.
 */
export function useLogStream(maxEvents = 200) {
  const [events, setEvents] = useState<LogEvent[]>([])
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const pingRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    const ws = new WebSocket(`${WS_BASE}/ws/logs`)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      // Ping every 30s to keep alive
      pingRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send('ping')
      }, 30_000)
    }

    ws.onmessage = (msg) => {
      try {
        const data = JSON.parse(msg.data)
        const event = toLogEvent(data)
        if (!event) return
        setEvents((prev: LogEvent[]) => {
          const next = [event, ...prev]
          return next.length > maxEvents ? next.slice(0, maxEvents) : next
        })
      } catch {
        // ignore parse errors
      }
    }

    ws.onclose = () => setConnected(false)
    ws.onerror = () => setConnected(false)

    return () => {
      if (pingRef.current) clearInterval(pingRef.current)
      ws.close()
    }
  }, [maxEvents])

  const clear = () => setEvents([])

  return { events, connected, clear }
}
