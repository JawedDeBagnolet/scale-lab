import { useMemo, useState } from 'react'
import { ChartLine, Eye, TrendDown, TrendUp } from '@phosphor-icons/react'
import { Empty, ErrorState, Loading } from '../../components/StateBlock'
import { useComptes, useStats, useStatsOverview } from '../../hooks/useApi'
import type { DailyStat, StatFilters } from '../../types/statistique'

// --- Date helpers ------------------------------------------------------------

function daysAgo(n: number): string {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return d.toISOString().slice(0, 10)
}

const RANGE_OPTIONS = [
  { label: '7 jours', days: 7 },
  { label: '30 jours', days: 30 },
  { label: '90 jours', days: 90 },
] as const

// --- KPI card ----------------------------------------------------------------

function KpiCard({
  icon: Icon,
  color,
  label,
  value,
  sub,
}: {
  icon: typeof ChartLine
  color: string
  label: string
  value: string
  sub?: string
}) {
  return (
    <div className="card flex items-center gap-4 px-5 py-5">
      <div
        className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl"
        style={{ background: `${color}20` }}
      >
        <Icon size={22} style={{ color }} />
      </div>
      <div>
        <div className="text-2xl font-bold tabular-nums">{value}</div>
        <div className="text-xs text-muted">{label}</div>
        {sub && <div className="mt-0.5 text-[11px] text-dim">{sub}</div>}
      </div>
    </div>
  )
}

// --- Sparkline ---------------------------------------------------------------

function Sparkline({ data, color }: { data: number[]; color: string }) {
  if (data.length < 2) return null
  const max = Math.max(...data)
  const min = Math.min(...data)
  const range = max - min || 1
  const w = 320
  const h = 80
  const pad = 2

  const points = data
    .map((v, i) => {
      const x = pad + (i / (data.length - 1)) * (w - pad * 2)
      const y = h - pad - ((v - min) / range) * (h - pad * 2)
      return `${x},${y}`
    })
    .join(' ')

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full" style={{ maxHeight: 120 }}>
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

// --- Stats table -------------------------------------------------------------

function StatsTable({ stats }: { stats: DailyStat[] }) {
  return (
    <div className="card overflow-hidden">
      <table className="w-full text-left text-[13px]">
        <thead>
          <tr className="border-b border-line text-[11px] uppercase tracking-wider text-muted">
            <th className="px-5 py-3 font-semibold">Date</th>
            <th className="px-5 py-3 font-semibold text-right">Abonnes</th>
            <th className="px-5 py-3 font-semibold text-right">Gagnes</th>
            <th className="px-5 py-3 font-semibold text-right">Perdus</th>
            <th className="px-5 py-3 font-semibold text-right">Portee</th>
            <th className="px-5 py-3 font-semibold text-right">Impressions</th>
            <th className="px-5 py-3 font-semibold text-right">Engagements</th>
            <th className="px-5 py-3 font-semibold text-right">Dispo.</th>
          </tr>
        </thead>
        <tbody>
          {stats.map((s) => (
            <tr
              key={s.id}
              className="border-b border-line last:border-0 hover:bg-white/[0.02]"
            >
              <td className="px-5 py-3 font-mono text-xs text-muted">
                {new Date(s.date).toLocaleDateString('fr-FR')}
              </td>
              <td className="px-5 py-3 text-right tabular-nums">
                {s.followers.toLocaleString('fr-FR')}
              </td>
              <td className="px-5 py-3 text-right tabular-nums text-success">
                +{s.gained.toLocaleString('fr-FR')}
              </td>
              <td className="px-5 py-3 text-right tabular-nums text-error">
                -{s.lost.toLocaleString('fr-FR')}
              </td>
              <td className="px-5 py-3 text-right tabular-nums">
                {s.reach.toLocaleString('fr-FR')}
              </td>
              <td className="px-5 py-3 text-right tabular-nums">
                {s.impressions.toLocaleString('fr-FR')}
              </td>
              <td className="px-5 py-3 text-right tabular-nums">
                {s.engagements.toLocaleString('fr-FR')}
              </td>
              <td className="px-5 py-3 text-right tabular-nums">
                {Math.round(s.availability * 100)}%
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// --- Main page ---------------------------------------------------------------

export default function StatistiquesPage() {
  const comptes = useComptes()
  const [compteId, setCompteId] = useState<string>('')
  const [rangeDays, setRangeDays] = useState<number>(30)
  const [customFrom, setCustomFrom] = useState('')
  const [customTo, setCustomTo] = useState('')

  const isCustom = rangeDays === 0

  const filters: StatFilters | null = useMemo(() => {
    if (!compteId) return null
    if (isCustom) {
      return {
        compte_id: compteId,
        date_from: customFrom || undefined,
        date_to: customTo || undefined,
      }
    }
    return {
      compte_id: compteId,
      date_from: daysAgo(rangeDays),
      date_to: daysAgo(0),
    }
  }, [compteId, rangeDays, isCustom, customFrom, customTo])

  const stats = useStats(filters ?? { compte_id: '' })
  const overview = useStatsOverview(compteId || undefined)

  // Auto-select first compte
  const comptesList = comptes.data ?? []
  if (comptesList.length > 0 && !compteId) {
    // Will update on next render
    setTimeout(() => setCompteId(comptesList[0].id), 0)
  }

  const selectedCompte = comptesList.find((c) => c.id === compteId)

  // Sparkline data (followers over time)
  const sparklineData = useMemo(
    () => (stats.data ?? []).map((s) => s.followers),
    [stats.data],
  )

  const ov = overview.data

  return (
    <div className="space-y-6">
      {/* Filters bar */}
      <div className="flex items-center gap-3 flex-wrap">
        <select
          className="field w-56"
          aria-label="Compte"
          value={compteId}
          onChange={(e) => setCompteId(e.target.value)}
        >
          <option value="">Selectionner un compte</option>
          {comptesList.map((c) => (
            <option key={c.id} value={c.id}>
              @{c.handle} ({c.plateforme.toUpperCase()})
            </option>
          ))}
        </select>

        <div className="flex gap-1">
          {RANGE_OPTIONS.map((opt) => (
            <button
              key={opt.days}
              type="button"
              className={`btn ${rangeDays === opt.days && !isCustom ? 'btn-primary' : 'btn-ghost'}`}
              onClick={() => setRangeDays(opt.days)}
            >
              {opt.label}
            </button>
          ))}
          <button
            type="button"
            className={`btn ${isCustom ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => setRangeDays(0)}
          >
            Personnalise
          </button>
        </div>

        {isCustom && (
          <div className="flex items-center gap-2">
            <label className="label text-xs">Du</label>
            <input
              type="date"
              className="field w-40"
              value={customFrom}
              onChange={(e) => setCustomFrom(e.target.value)}
            />
            <label className="label text-xs">Au</label>
            <input
              type="date"
              className="field w-40"
              value={customTo}
              onChange={(e) => setCustomTo(e.target.value)}
            />
          </div>
        )}

        {selectedCompte && (
          <span className="ml-auto text-[13px] text-muted">
            {stats.data ? `${stats.data.length} jour${stats.data.length > 1 ? 's' : ''}` : ''}
          </span>
        )}
      </div>

      {/* No compte selected */}
      {!compteId && (
        <Empty>Selectionnez un compte pour afficher les statistiques.</Empty>
      )}

      {/* Loading / Error */}
      {compteId && stats.isLoading && <Loading />}
      {compteId && stats.isError && (
        <ErrorState error={stats.error} onRetry={() => stats.refetch()} />
      )}

      {/* KPI row */}
      {compteId && ov && (
        <div className="grid grid-cols-4 gap-4">
          <KpiCard
            icon={TrendUp}
            color="#6d5ef0"
            label="Abonnes"
            value={ov.total_followers.toLocaleString('fr-FR')}
          />
          <KpiCard
            icon={ChartLine}
            color="#4b7bf5"
            label="Taux d'engagement"
            value={`${ov.avg_engagement_rate.toFixed(2)}%`}
          />
          <KpiCard
            icon={Eye}
            color="#22c55e"
            label="Portee (30j)"
            value={ov.total_reach_30d.toLocaleString('fr-FR')}
          />
          <KpiCard
            icon={TrendDown}
            color="#f59e0b"
            label="Meilleur jour"
            value={
              ov.best_day
                ? new Date(ov.best_day).toLocaleDateString('fr-FR', {
                    day: 'numeric',
                    month: 'short',
                  })
                : '—'
            }
          />
        </div>
      )}

      {/* Chart area */}
      {compteId && stats.data && stats.data.length > 1 && (
        <div className="card px-5 py-5">
          <h2 className="mb-3 text-sm font-bold">Evolution des abonnes</h2>
          <Sparkline data={sparklineData} color="#6d5ef0" />
        </div>
      )}

      {/* Stats table */}
      {compteId && stats.data && stats.data.length > 0 && (
        <StatsTable stats={stats.data} />
      )}

      {compteId && stats.data && stats.data.length === 0 && !stats.isLoading && (
        <Empty>Aucune statistique pour cette periode.</Empty>
      )}
    </div>
  )
}
