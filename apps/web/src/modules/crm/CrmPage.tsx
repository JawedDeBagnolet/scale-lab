import { useSearchParams } from 'react-router-dom'
import {
  ChartBar,
  CurrencyDollar,
  FileText,
  Star,
  Users,
} from '@phosphor-icons/react'
import { Empty, ErrorState, Loading } from '../../components/StateBlock'
import {
  useCrmOverview,
  useFans,
  usePersonas,
  useScripts,
  useTransactions,
} from '../../hooks/useApi'
import type {
  Fan,
  FanFilters,
  Script,
  ScriptFilters,
  Transaction,
  TransactionFilters,
  TransactionType,
} from '../../types/crm'

type Tab = 'overview' | 'fans' | 'transactions' | 'scripts'

const TABS: { key: Tab; label: string }[] = [
  { key: 'overview', label: "Vue d'ensemble" },
  { key: 'fans', label: 'Fans' },
  { key: 'transactions', label: 'Transactions' },
  { key: 'scripts', label: 'Scripts' },
]

const TX_TYPE_LABELS: Record<TransactionType, string> = {
  sub: 'Abo',
  ppv: 'PPV',
  tip: 'Tip',
}

const TX_TYPE_COLORS: Record<TransactionType, string> = {
  sub: '#6d5ef0',
  ppv: '#4b7bf5',
  tip: '#22c55e',
}

// --- KPI card ----------------------------------------------------------------

function KpiCard({
  icon: Icon,
  color,
  label,
  value,
  sub,
}: {
  icon: typeof Users
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

// --- Overview tab -------------------------------------------------------------

function OverviewTab() {
  const overview = useCrmOverview()

  if (overview.isLoading) return <Loading />
  if (overview.isError) return <ErrorState error={overview.error} onRetry={() => overview.refetch()} />
  if (!overview.data) return null

  const ov = overview.data

  return (
    <div className="grid grid-cols-4 gap-4">
      <KpiCard
        icon={Users}
        color="#6d5ef0"
        label="Fans total"
        value={ov.total_fans.toLocaleString('fr-FR')}
      />
      <KpiCard
        icon={CurrencyDollar}
        color="#22c55e"
        label="Revenu total"
        value={`${ov.total_revenue.toLocaleString('fr-FR')} $`}
      />
      <KpiCard
        icon={ChartBar}
        color="#4b7bf5"
        label="LTV moyen"
        value={`${ov.avg_ltv.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} $`}
      />
      <KpiCard
        icon={FileText}
        color="#f59e0b"
        label="Meilleur script"
        value={ov.top_script ?? '—'}
      />
    </div>
  )
}

// --- Fans tab ----------------------------------------------------------------

function FansTab() {
  const [params, setParams] = useSearchParams()
  const creatorId = params.get('creator_id') ?? undefined
  const platform = params.get('platform_origin') ?? undefined

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    // Keep tab param
    next.set('tab', 'fans')
    setParams(next, { replace: true })
  }

  const filters: FanFilters = { creator_id: creatorId, platform_origin: platform }
  const fans = useFans(filters)
  const personas = usePersonas()

  const personaMap = new Map(
    (personas.data ?? []).map((p) => [p.id, `${p.first_name}${p.last_name ? ` ${p.last_name}` : ''}`]),
  )

  const platforms = [...new Set(fans.data?.map((f) => f.platform_origin) ?? [])].sort()

  return (
    <div>
      <div className="mb-4 flex items-center gap-3">
        <select
          className="field w-52"
          aria-label="Filtrer par creator"
          value={creatorId ?? ''}
          onChange={(e) => setFilter('creator_id', e.target.value)}
        >
          <option value="">Tous les creators</option>
          {(personas.data ?? []).map((p) => (
            <option key={p.id} value={p.id}>
              {p.first_name}{p.last_name ? ` ${p.last_name}` : ''}
            </option>
          ))}
        </select>
        <select
          className="field w-40"
          aria-label="Filtrer par plateforme"
          value={platform ?? ''}
          onChange={(e) => setFilter('platform_origin', e.target.value)}
        >
          <option value="">Toutes les plateformes</option>
          {platforms.map((pl) => (
            <option key={pl} value={pl}>
              {pl.toUpperCase()}
            </option>
          ))}
        </select>
        <span className="text-xs text-muted">
          {fans.data ? `${fans.data.length} fan${fans.data.length > 1 ? 's' : ''}` : ''}
        </span>
      </div>

      {fans.isLoading && <Loading />}
      {fans.isError && <ErrorState error={fans.error} onRetry={() => fans.refetch()} />}
      {fans.data?.length === 0 && <Empty>Aucun fan pour le moment.</Empty>}

      {fans.data && fans.data.length > 0 && (
        <div className="card overflow-hidden">
          <table className="w-full text-left text-[13px]">
            <thead>
              <tr className="border-b border-line text-[11px] uppercase tracking-wider text-muted">
                <th className="px-5 py-3 font-semibold">Pseudo</th>
                <th className="px-5 py-3 font-semibold">Creator</th>
                <th className="px-5 py-3 font-semibold">Plateforme</th>
                <th className="px-5 py-3 font-semibold">Rejoint le</th>
                <th className="px-5 py-3 font-semibold text-right">Total depense</th>
                <th className="px-5 py-3 font-semibold">Derniere activite</th>
                <th className="px-5 py-3 font-semibold">Notes</th>
              </tr>
            </thead>
            <tbody>
              {fans.data.map((f: Fan) => (
                <tr
                  key={f.id}
                  className="border-b border-line last:border-0 hover:bg-white/[0.02]"
                >
                  <td className="px-5 py-3 font-semibold">{f.pseudo}</td>
                  <td className="px-5 py-3 text-muted">
                    {personaMap.get(f.creator_id) ?? f.creator_id.slice(0, 8)}
                  </td>
                  <td className="px-5 py-3">
                    <span className="rounded-md bg-white/[0.06] px-2 py-0.5 text-xs font-semibold uppercase">
                      {f.platform_origin}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-muted text-xs">
                    {new Date(f.joined_at).toLocaleDateString('fr-FR')}
                  </td>
                  <td className="px-5 py-3 text-right tabular-nums font-semibold">
                    {f.total_spent.toLocaleString('fr-FR')} $
                  </td>
                  <td className="px-5 py-3 text-muted text-xs">
                    {f.last_activity
                      ? new Date(f.last_activity).toLocaleDateString('fr-FR')
                      : '—'}
                  </td>
                  <td className="max-w-[200px] truncate px-5 py-3 text-muted text-xs">
                    {f.notes ?? '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// --- Transactions tab --------------------------------------------------------

function TransactionsTab() {
  const [params, setParams] = useSearchParams()
  const creatorId = params.get('creator_id') ?? undefined
  const txType = params.get('type') as TransactionType | undefined
  const dateFrom = params.get('date_from') ?? undefined
  const dateTo = params.get('date_to') ?? undefined

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    next.set('tab', 'transactions')
    setParams(next, { replace: true })
  }

  const filters: TransactionFilters = {
    creator_id: creatorId,
    type: txType,
    date_from: dateFrom,
    date_to: dateTo,
  }
  const transactions = useTransactions(filters)
  const personas = usePersonas()
  const fans = useFans()

  const fanMap = new Map((fans.data ?? []).map((f) => [f.id, f.pseudo]))

  return (
    <div>
      <div className="mb-4 flex items-center gap-3 flex-wrap">
        <select
          className="field w-52"
          aria-label="Filtrer par creator"
          value={creatorId ?? ''}
          onChange={(e) => setFilter('creator_id', e.target.value)}
        >
          <option value="">Tous les creators</option>
          {(personas.data ?? []).map((p) => (
            <option key={p.id} value={p.id}>
              {p.first_name}{p.last_name ? ` ${p.last_name}` : ''}
            </option>
          ))}
        </select>
        <select
          className="field w-36"
          aria-label="Filtrer par type"
          value={txType ?? ''}
          onChange={(e) => setFilter('type', e.target.value)}
        >
          <option value="">Tous les types</option>
          <option value="sub">Abo</option>
          <option value="ppv">PPV</option>
          <option value="tip">Tip</option>
        </select>
        <div className="flex items-center gap-2">
          <label className="label text-xs">Du</label>
          <input
            type="date"
            className="field w-40"
            value={dateFrom ?? ''}
            onChange={(e) => setFilter('date_from', e.target.value)}
          />
          <label className="label text-xs">Au</label>
          <input
            type="date"
            className="field w-40"
            value={dateTo ?? ''}
            onChange={(e) => setFilter('date_to', e.target.value)}
          />
        </div>
        <span className="text-xs text-muted">
          {transactions.data
            ? `${transactions.data.length} transaction${transactions.data.length > 1 ? 's' : ''}`
            : ''}
        </span>
      </div>

      {transactions.isLoading && <Loading />}
      {transactions.isError && (
        <ErrorState error={transactions.error} onRetry={() => transactions.refetch()} />
      )}
      {transactions.data?.length === 0 && <Empty>Aucune transaction pour le moment.</Empty>}

      {transactions.data && transactions.data.length > 0 && (
        <div className="card overflow-hidden">
          <table className="w-full text-left text-[13px]">
            <thead>
              <tr className="border-b border-line text-[11px] uppercase tracking-wider text-muted">
                <th className="px-5 py-3 font-semibold">Date</th>
                <th className="px-5 py-3 font-semibold">Fan</th>
                <th className="px-5 py-3 font-semibold">Type</th>
                <th className="px-5 py-3 font-semibold text-right">Montant</th>
                <th className="px-5 py-3 font-semibold">Script</th>
              </tr>
            </thead>
            <tbody>
              {transactions.data.map((tx: Transaction) => {
                const typeKey = tx.transaction_type as TransactionType
                return (
                  <tr
                    key={tx.id}
                    className="border-b border-line last:border-0 hover:bg-white/[0.02]"
                  >
                    <td className="px-5 py-3 font-mono text-xs text-muted">
                      {new Date(tx.timestamp).toLocaleString('fr-FR', {
                        day: '2-digit',
                        month: '2-digit',
                        year: '2-digit',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </td>
                    <td className="px-5 py-3">
                      {fanMap.get(tx.fan_id) ?? tx.fan_id.slice(0, 8)}
                    </td>
                    <td className="px-5 py-3">
                      <span
                        className="inline-block rounded-md px-2 py-0.5 text-xs font-bold"
                        style={{
                          background: `${TX_TYPE_COLORS[typeKey] ?? '#8b8fa3'}20`,
                          color: TX_TYPE_COLORS[typeKey] ?? '#8b8fa3',
                        }}
                      >
                        {TX_TYPE_LABELS[typeKey] ?? tx.transaction_type}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-right tabular-nums font-semibold">
                      {tx.amount.toLocaleString('fr-FR')} $
                    </td>
                    <td className="px-5 py-3 text-muted text-xs">
                      {tx.script_id ? tx.script_id.slice(0, 8) : '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// --- Scripts tab -------------------------------------------------------------

function ScriptsTab() {
  const [params, setParams] = useSearchParams()
  const activeParam = params.get('active')
  const folder = params.get('folder') ?? undefined

  const active =
    activeParam === 'true' ? true : activeParam === 'false' ? false : undefined

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    next.set('tab', 'scripts')
    setParams(next, { replace: true })
  }

  const filters: ScriptFilters = { active, folder }
  const scripts = useScripts(filters)

  const folders = [...new Set(scripts.data?.map((s) => s.folder).filter(Boolean) ?? [])].sort() as string[]

  return (
    <div>
      <div className="mb-4 flex items-center gap-3">
        <select
          className="field w-44"
          aria-label="Filtrer par statut"
          value={activeParam ?? ''}
          onChange={(e) => setFilter('active', e.target.value)}
        >
          <option value="">Tous les statuts</option>
          <option value="true">Actif</option>
          <option value="false">Inactif</option>
        </select>
        <select
          className="field w-44"
          aria-label="Filtrer par dossier"
          value={folder ?? ''}
          onChange={(e) => setFilter('folder', e.target.value)}
        >
          <option value="">Tous les dossiers</option>
          {folders.map((f) => (
            <option key={f} value={f}>
              {f}
            </option>
          ))}
        </select>
        <span className="text-xs text-muted">
          {scripts.data
            ? `${scripts.data.length} script${scripts.data.length > 1 ? 's' : ''}`
            : ''}
        </span>
      </div>

      {scripts.isLoading && <Loading />}
      {scripts.isError && <ErrorState error={scripts.error} onRetry={() => scripts.refetch()} />}
      {scripts.data?.length === 0 && <Empty>Aucun script pour le moment.</Empty>}

      {scripts.data && scripts.data.length > 0 && (
        <div className="grid grid-cols-3 gap-4">
          {scripts.data.map((s: Script) => (
            <ScriptCard key={s.id} script={s} />
          ))}
        </div>
      )}
    </div>
  )
}

function ScriptCard({ script: s }: { script: Script }) {
  const stepCount = s.steps?.length ?? 0
  const stats = s.stats as Record<string, unknown> | null
  const sends = (stats?.sends as number) ?? 0
  const opens = (stats?.opens as number) ?? 0
  const unlocks = (stats?.unlocks as number) ?? 0
  const revenue = (stats?.revenue as number) ?? 0

  return (
    <div className="card px-5 py-5 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FileText size={18} className="text-muted" />
          <span className="font-semibold text-sm">{s.folder ?? 'Sans dossier'}</span>
        </div>
        <div className="flex items-center gap-2">
          {s.priority && (
            <Star size={16} weight="fill" className="text-warning" />
          )}
          <span
            className={`rounded-md px-2 py-0.5 text-[11px] font-bold ${
              s.active
                ? 'bg-success/15 text-success'
                : 'bg-white/[0.06] text-muted'
            }`}
          >
            {s.active ? 'Actif' : 'Inactif'}
          </span>
        </div>
      </div>

      <div className="text-xs text-muted">
        {stepCount} etape{stepCount > 1 ? 's' : ''}
      </div>

      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
        <div className="flex justify-between">
          <span className="text-muted">Envois</span>
          <span className="tabular-nums font-semibold">{sends.toLocaleString('fr-FR')}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted">Ouvertures</span>
          <span className="tabular-nums font-semibold">{opens.toLocaleString('fr-FR')}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted">Unlocks</span>
          <span className="tabular-nums font-semibold">{unlocks.toLocaleString('fr-FR')}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted">Revenu</span>
          <span className="tabular-nums font-semibold">{revenue.toLocaleString('fr-FR')} $</span>
        </div>
      </div>

      <div className="text-[11px] text-dim">
        Cree le {new Date(s.created_at).toLocaleDateString('fr-FR')}
      </div>
    </div>
  )
}

// --- Main page ---------------------------------------------------------------

export default function CrmPage() {
  const [params, setParams] = useSearchParams()
  const currentTab = (params.get('tab') as Tab) || 'overview'

  const setTab = (key: Tab) => {
    const next = new URLSearchParams()
    next.set('tab', key)
    setParams(next, { replace: true })
  }

  return (
    <div className="space-y-6">
      <div className="flex gap-1 rounded-xl bg-white/[0.03] p-1">
        {TABS.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            className={`rounded-lg px-4 py-2 text-[13px] font-semibold transition-colors ${
              currentTab === key
                ? 'bg-accent-1/15 text-white'
                : 'text-muted hover:text-white'
            }`}
            onClick={() => setTab(key)}
          >
            {label}
          </button>
        ))}
      </div>

      {currentTab === 'overview' && <OverviewTab />}
      {currentTab === 'fans' && <FansTab />}
      {currentTab === 'transactions' && <TransactionsTab />}
      {currentTab === 'scripts' && <ScriptsTab />}
    </div>
  )
}
