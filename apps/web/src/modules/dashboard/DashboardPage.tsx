import { Link } from 'react-router-dom'
import {
  ChartLine,
  Crosshair,
  Lightning,
  SlidersHorizontal,
  UserCircle,
  UsersThree,
  WarningCircle,
} from '@phosphor-icons/react'
import { ErrorState, Loading } from '../../components/StateBlock'
import { useDashboardStats, useEvents, useIncidents } from '../../hooks/useApi'
import {
  INCIDENT_STATUS_COLORS,
  LEVEL_COLORS,
  type EventLevel,
  type IncidentStatus,
} from '../../types/log'

// --- KPI card ----------------------------------------------------------------

function KpiCard({
  icon: Icon,
  color,
  label,
  value,
  sub,
  to,
}: {
  icon: typeof ChartLine
  color: string
  label: string
  value: number
  sub?: string
  to?: string
}) {
  const card = (
    <div className="card flex items-center gap-4 px-5 py-5 transition-colors hover:border-white/10">
      <div
        className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl"
        style={{ background: `${color}20` }}
      >
        <Icon size={22} style={{ color }} />
      </div>
      <div>
        <div className="text-2xl font-bold tabular-nums">{value.toLocaleString('fr-FR')}</div>
        <div className="text-xs text-muted">{label}</div>
        {sub && <div className="mt-0.5 text-[11px] text-dim">{sub}</div>}
      </div>
    </div>
  )

  return to ? <Link to={to}>{card}</Link> : card
}

// --- Recent events -----------------------------------------------------------

function RecentEvents() {
  const events = useEvents({ limit: 8 })

  if (!events.data || events.data.length === 0) return null

  return (
    <section className="card overflow-hidden">
      <div className="flex items-center justify-between border-b border-line px-5 py-3">
        <h2 className="text-sm font-bold">Derniers evenements</h2>
        <Link to="/logs" className="text-xs font-semibold text-accent-2 hover:underline">
          Voir tout
        </Link>
      </div>
      <table className="w-full text-left text-[13px]">
        <tbody>
          {events.data.map((e) => {
            const ts = new Date(e.timestamp)
            return (
              <tr key={e.id} className="border-b border-line last:border-0 hover:bg-white/[0.02]">
                <td className="whitespace-nowrap px-5 py-2.5 font-mono text-xs text-muted">
                  {ts.toLocaleTimeString('fr-FR')}
                </td>
                <td className="px-3 py-2.5">
                  <span
                    className="inline-block h-2 w-2 rounded-full"
                    style={{
                      background:
                        LEVEL_COLORS[e.level as EventLevel] ?? 'var(--text-muted)',
                    }}
                  />
                </td>
                <td className="px-3 py-2.5 text-muted">{e.module}</td>
                <td className="max-w-xs truncate px-3 py-2.5">{e.message}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </section>
  )
}

// --- Open incidents ----------------------------------------------------------

function OpenIncidents() {
  const incidents = useIncidents({ status: 'open' })

  if (!incidents.data || incidents.data.length === 0) return null

  return (
    <section className="card overflow-hidden">
      <div className="flex items-center justify-between border-b border-line px-5 py-3">
        <h2 className="flex items-center gap-2 text-sm font-bold">
          <WarningCircle size={16} className="text-warning" /> Incidents ouverts
        </h2>
        <Link to="/logs" className="text-xs font-semibold text-accent-2 hover:underline">
          Gerer
        </Link>
      </div>
      <div className="divide-y divide-line">
        {incidents.data.slice(0, 5).map((inc) => (
          <div key={inc.id} className="flex items-center gap-4 px-5 py-3">
            <span
              className="inline-flex h-2.5 w-2.5 shrink-0 rounded-full"
              style={{
                background:
                  INCIDENT_STATUS_COLORS[inc.status as IncidentStatus],
              }}
            />
            <div className="min-w-0 flex-1">
              <span className="font-semibold">{inc.module}</span>
              <span className="ml-2 text-xs text-muted">{inc.event_type}</span>
            </div>
            <span className="text-xs text-muted tabular-nums">
              {inc.event_count}x
            </span>
            <span className="text-xs text-dim">
              {new Date(inc.last_seen).toLocaleDateString('fr-FR')}
            </span>
          </div>
        ))}
      </div>
    </section>
  )
}

// --- Main page ---------------------------------------------------------------

export default function DashboardPage() {
  const stats = useDashboardStats()

  if (stats.isLoading) return <Loading />
  if (stats.isError) return <ErrorState error={stats.error} onRetry={() => stats.refetch()} />

  const s = stats.data!

  return (
    <div className="space-y-6">
      {/* KPI Grid */}
      <div className="grid grid-cols-4 gap-4">
        <KpiCard
          icon={UserCircle}
          color="#6d5ef0"
          label="Personas"
          value={s.total_personas}
          to="/personas"
        />
        <KpiCard
          icon={UsersThree}
          color="#4b7bf5"
          label="Comptes"
          value={s.total_comptes}
          sub={`${s.comptes_ok} OK · ${s.comptes_error} en erreur`}
          to="/comptes"
        />
        <KpiCard
          icon={Crosshair}
          color="#22c55e"
          label="Targets"
          value={s.total_targets}
          to="/targets"
        />
        <KpiCard
          icon={SlidersHorizontal}
          color="#f59e0b"
          label="Presets"
          value={s.total_presets}
          to="/comportements"
        />
      </div>

      {/* Alerts row */}
      <div className="grid grid-cols-3 gap-4">
        <KpiCard
          icon={Lightning}
          color="var(--accent-2)"
          label="Evenements"
          value={s.total_events}
          to="/logs"
        />
        <KpiCard
          icon={WarningCircle}
          color="var(--error)"
          label="Erreurs (24h)"
          value={s.errors_24h}
          to="/logs"
        />
        <KpiCard
          icon={WarningCircle}
          color="var(--warning)"
          label="Incidents ouverts"
          value={s.open_incidents}
          to="/logs"
        />
      </div>

      {/* Recent activity */}
      <div className="grid grid-cols-2 gap-5">
        <RecentEvents />
        <OpenIncidents />
      </div>
    </div>
  )
}
