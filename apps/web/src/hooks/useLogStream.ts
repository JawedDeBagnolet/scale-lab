import { useEffect, useRef, useState } from 'react'
import type { LogEvent } from '../types/log'

const WS_BASE = (import.meta.env.VITE_API_BASE || 'https://api.scalelab.win')
  .replace(/^http/, 'ws')

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
        if (data.type === 'pong') return
        // Treat as a log event
        setEvents((prev) => {
          const next = [data as LogEvent, ...prev]
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
