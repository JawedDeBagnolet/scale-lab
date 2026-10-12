import { useState } from 'react'
import {
  Bell,
  CheckCircle,
  Circle,
  Lightning,
  Plus,
  Trash,
  WarningCircle,
  WifiHigh,
  WifiSlash,
  XCircle,
} from '@phosphor-icons/react'
import ConfirmDialog from '../../components/ConfirmDialog'
import Modal from '../../components/Modal'
import { Empty, ErrorState, Loading } from '../../components/StateBlock'
import {
  useAlertRules,
  useCreateAlertRule,
  useDeleteAlertRule,
  useEvents,
  useIncidents,
  useLogStats,
  useUpdateIncident,
} from '../../hooks/useApi'
import { useLogStream } from '../../hooks/useLogStream'
import {
  EVENT_LEVELS,
  INCIDENT_STATUSES,
  INCIDENT_STATUS_COLORS,
  INCIDENT_STATUS_LABELS,
  LEVEL_COLORS,
  type AlertRule,
  type AlertRuleCreate,
  type EventLevel,
  type Incident,
  type IncidentStatus,
  type LogEvent,
} from '../../types/log'

type Tab = 'live' | 'events' | 'incidents' | 'rules'

// --- Stats bar ---------------------------------------------------------------

function StatsBar() {
  const stats = useLogStats()
  if (!stats.data) return null

  const items = [
    { label: 'Evenements total', value: stats.data.total_events, color: 'var(--accent-2)' },
    { label: 'Erreurs (24h)', value: stats.data.errors_24h, color: 'var(--error)' },
    { label: 'Incidents ouverts', value: stats.data.open_incidents, color: 'var(--warning)' },
  ]

  return (
    <div className="mb-6 grid grid-cols-3 gap-4">
      {items.map(({ label, value, color }) => (
        <div key={label} className="card flex items-center gap-4 px-5 py-4">
          <div
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl"
            style={{ background: `${color}20` }}
          >
            <Lightning size={20} style={{ color }} />
          </div>
          <div>
            <div className="text-2xl font-bold tabular-nums">{value.toLocaleString('fr-FR')}</div>
            <div className="text-xs text-muted">{label}</div>
          </div>
        </div>
      ))}
    </div>
  )
}

// --- Live tab ----------------------------------------------------------------

function LiveTab() {
  const { events, connected, clear } = useLogStream()
  const [levelFilter, setLevelFilter] = useState<EventLevel | ''>('')

  const filtered = levelFilter ? events.filter((e) => e.level === levelFilter) : events

  return (
    <div>
      <div className="mb-4 flex items-center gap-3">
        <span
          className={`inline-flex items-center gap-1.5 text-xs font-semibold ${
            connected ? 'text-success' : 'text-error'
          }`}
        >
          {connected ? <WifiHigh size={14} /> : <WifiSlash size={14} />}
          {connected ? 'Connecte' : 'Deconnecte'}
        </span>
        <select
          className="field w-36"
          value={levelFilter}
          onChange={(e) => setLevelFilter(e.target.value as EventLevel | '')}
        >
          <option value="">Tous les niveaux</option>
          {EVENT_LEVELS.map((l) => (
            <option key={l} value={l}>
              {l.charAt(0).toUpperCase() + l.slice(1)}
            </option>
          ))}
        </select>
        <span className="text-xs text-muted">{filtered.length} evenement(s)</span>
        {events.length > 0 && (
          <button type="button" className="btn btn-ghost ml-auto text-xs" onClick={clear}>
            Vider
          </button>
        )}
      </div>

      {filtered.length === 0 ? (
        <Empty>Aucun evenement en direct. Les evenements apparaitront ici en temps reel.</Empty>
      ) : (
        <div className="card overflow-hidden">
          <div className="max-h-[60vh] overflow-y-auto">
            <table className="w-full text-left text-[13px]">
              <thead className="sticky top-0 bg-card">
                <tr className="border-b border-line text-[11px] uppercase tracking-wider text-muted">
                  <th className="px-4 py-2 font-semibold">Heure</th>
                  <th className="px-4 py-2 font-semibold">Niveau</th>
                  <th className="px-4 py-2 font-semibold">Module</th>
                  <th className="px-4 py-2 font-semibold">Message</th>
                  <th className="px-4 py-2 font-semibold">Target</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((e, i) => (
                  <EventRow key={e.id ?? i} event={e} />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

// --- Events tab --------------------------------------------------------------

function EventsTab() {
  const [module, setModule] = useState('')
  const [level, setLevel] = useState<EventLevel | ''>('')
  const events = useEvents({ module: module || undefined, level: level || undefined, limit: 200 })

  return (
    <div>
      <div className="mb-4 flex items-center gap-3">
        <input
          className="field w-44"
          placeholder="Filtrer par module"
          value={module}
          onChange={(e) => setModule(e.target.value)}
        />
        <select
          className="field w-36"
          value={level}
          onChange={(e) => setLevel(e.target.value as EventLevel | '')}
        >
          <option value="">Tous les niveaux</option>
          {EVENT_LEVELS.map((l) => (
            <option key={l} value={l}>
              {l.charAt(0).toUpperCase() + l.slice(1)}
            </option>
          ))}
        </select>
        <span className="text-xs text-muted">
          {events.data ? `${events.data.length} evenement(s)` : ''}
        </span>
      </div>

      {events.isLoading && <Loading />}
      {events.isError && <ErrorState error={events.error} onRetry={() => events.refetch()} />}
      {events.data?.length === 0 && <Empty>Aucun evenement enregistre.</Empty>}

      {events.data && events.data.length > 0 && (
        <div className="card overflow-hidden">
          <div className="max-h-[60vh] overflow-y-auto">
            <table className="w-full text-left text-[13px]">
              <thead className="sticky top-0 bg-card">
                <tr className="border-b border-line text-[11px] uppercase tracking-wider text-muted">
                  <th className="px-4 py-2 font-semibold">Date</th>
                  <th className="px-4 py-2 font-semibold">Niveau</th>
                  <th className="px-4 py-2 font-semibold">Module</th>
                  <th className="px-4 py-2 font-semibold">Type</th>
                  <th className="px-4 py-2 font-semibold">Message</th>
                  <th className="px-4 py-2 font-semibold">Target</th>
                </tr>
              </thead>
              <tbody>
                {events.data.map((e) => (
                  <EventRow key={e.id} event={e} showDate />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

function EventRow({ event: e, showDate }: { event: LogEvent; showDate?: boolean }) {
  const ts = new Date(e.timestamp)
  return (
    <tr className="border-b border-line last:border-0 hover:bg-white/[0.02]">
      <td className="whitespace-nowrap px-4 py-2 font-mono text-xs text-muted">
        {showDate
          ? ts.toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })
          : ts.toLocaleTimeString('fr-FR')}
      </td>
      <td className="px-4 py-2">
        <span
          className="inline-flex items-center gap-1 text-xs font-semibold"
          style={{ color: LEVEL_COLORS[e.level as EventLevel] ?? 'var(--text-muted)' }}
        >
          {e.level === 'error' || e.level === 'critical' ? (
            <XCircle size={14} weight="fill" />
          ) : e.level === 'warning' ? (
            <WarningCircle size={14} weight="fill" />
          ) : (
            <Circle size={12} weight="fill" />
          )}
          {e.level}
        </span>
      </td>
      <td className="px-4 py-2 text-muted">{e.module}</td>
      {showDate && <td className="px-4 py-2 text-muted">{e.event_type}</td>}
      <td className="max-w-xs truncate px-4 py-2">{e.message}</td>
      <td className="px-4 py-2 text-muted">{e.target ?? '—'}</td>
    </tr>
  )
}

// --- Incidents tab -----------------------------------------------------------

function IncidentsTab() {
  const [statusFilter, setStatusFilter] = useState<IncidentStatus | ''>('')
  const incidents = useIncidents({ status: statusFilter || undefined })
  const update = useUpdateIncident()

  return (
    <div>
      <div className="mb-4 flex items-center gap-3">
        <select
          className="field w-44"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as IncidentStatus | '')}
        >
          <option value="">Tous les statuts</option>
          {INCIDENT_STATUSES.map((s) => (
            <option key={s} value={s}>
              {INCIDENT_STATUS_LABELS[s]}
            </option>
          ))}
        </select>
        <span className="text-xs text-muted">
          {incidents.data ? `${incidents.data.length} incident(s)` : ''}
        </span>
      </div>

      {incidents.isLoading && <Loading />}
      {incidents.isError && (
        <ErrorState error={incidents.error} onRetry={() => incidents.refetch()} />
      )}
      {incidents.data?.length === 0 && <Empty>Aucun incident.</Empty>}

      {incidents.data && incidents.data.length > 0 && (
        <div className="space-y-3">
          {incidents.data.map((inc) => (
            <IncidentCard key={inc.id} incident={inc} onStatusChange={update} />
          ))}
        </div>
      )}
    </div>
  )
}

function IncidentCard({
  incident: inc,
  onStatusChange,
}: {
  incident: Incident
  onStatusChange: ReturnType<typeof useUpdateIncident>
}) {
  return (
    <div className="card flex items-center gap-5 px-5 py-4">
      <span
        className="inline-flex h-2.5 w-2.5 shrink-0 rounded-full"
        style={{ background: INCIDENT_STATUS_COLORS[inc.status as IncidentStatus] }}
      />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="font-semibold">{inc.module}</span>
          <span className="text-xs text-muted">{inc.event_type}</span>
          {inc.target && <span className="text-xs text-dim">@{inc.target}</span>}
        </div>
        <div className="mt-0.5 text-xs text-muted">
          {inc.event_count} occurence{inc.event_count > 1 ? 's' : ''} ·{' '}
          {new Date(inc.last_seen).toLocaleString('fr-FR')}
        </div>
      </div>
      <select
        className="field w-36"
        value={inc.status}
        onChange={(e) => onStatusChange.mutate({ id: inc.id, status: e.target.value })}
        disabled={onStatusChange.isPending}
      >
        {INCIDENT_STATUSES.map((s) => (
          <option key={s} value={s}>
            {INCIDENT_STATUS_LABELS[s]}
          </option>
        ))}
      </select>
    </div>
  )
}

// --- Alert rules tab ---------------------------------------------------------

function RulesTab() {
  const rules = useAlertRules()
  const del = useDeleteAlertRule()
  const [showCreate, setShowCreate] = useState(false)
  const [deleting, setDeleting] = useState<AlertRule | null>(null)

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <span className="text-xs text-muted">
          {rules.data ? `${rules.data.length} regle(s)` : ''}
        </span>
        <button type="button" className="btn btn-primary" onClick={() => setShowCreate(true)}>
          <Plus size={16} weight="bold" /> Nouvelle regle
        </button>
      </div>

      {rules.isLoading && <Loading />}
      {rules.isError && <ErrorState error={rules.error} onRetry={() => rules.refetch()} />}
      {rules.data?.length === 0 && (
        <Empty>Aucune regle d'alerte configuree.</Empty>
      )}

      {rules.data && rules.data.length > 0 && (
        <div className="card overflow-hidden">
          <table className="w-full text-left text-[13px]">
            <thead>
              <tr className="border-b border-line text-[11px] uppercase tracking-wider text-muted">
                <th className="px-5 py-3 font-semibold">Module</th>
                <th className="px-5 py-3 font-semibold">Type</th>
                <th className="px-5 py-3 text-right font-semibold">Seuil erreurs</th>
                <th className="px-5 py-3 text-right font-semibold">Seuil actions</th>
                <th className="px-5 py-3 font-semibold">Telegram</th>
                <th className="w-16 px-5 py-3" />
              </tr>
            </thead>
            <tbody>
              {rules.data.map((r) => (
                <tr
                  key={r.id}
                  className="border-b border-line last:border-0 hover:bg-white/[0.02]"
                >
                  <td className="px-5 py-3 font-semibold">{r.module}</td>
                  <td className="px-5 py-3 text-muted">{r.event_type}</td>
                  <td className="px-5 py-3 text-right tabular-nums">{r.threshold_errors}</td>
                  <td className="px-5 py-3 text-right tabular-nums">{r.threshold_actions}</td>
                  <td className="px-5 py-3">
                    {r.tg_enabled ? (
                      <CheckCircle size={16} className="text-success" weight="fill" />
                    ) : (
                      <XCircle size={16} className="text-dim" />
                    )}
                  </td>
                  <td className="px-5 py-3">
                    <button
                      type="button"
                      className="icon-btn"
                      aria-label="Supprimer"
                      onClick={() => setDeleting(r)}
                    >
                      <Trash size={16} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showCreate && <CreateRuleModal onClose={() => setShowCreate(false)} />}

      {deleting && (
        <ConfirmDialog
          title="Supprimer la regle"
          message={`La regle « ${deleting.module} / ${deleting.event_type} » sera supprimee.`}
          pending={del.isPending}
          onCancel={() => setDeleting(null)}
          onConfirm={() => del.mutate(deleting.id, { onSuccess: () => setDeleting(null) })}
        />
      )}
    </div>
  )
}

function CreateRuleModal({ onClose }: { onClose: () => void }) {
  const create = useCreateAlertRule()
  const [form, setForm] = useState<AlertRuleCreate>({
    module: '',
    event_type: '',
    threshold_errors: 3,
    threshold_actions: 10,
    tg_enabled: true,
  })

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    create.mutate(form, { onSuccess: onClose })
  }

  return (
    <Modal
      title="Nouvelle regle d'alerte"
      onClose={onClose}
      width={480}
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Annuler
          </button>
          <button
            type="submit"
            form="rule-form"
            className="btn btn-primary"
            disabled={create.isPending || !form.module.trim() || !form.event_type.trim()}
          >
            <Bell size={16} /> Creer
          </button>
        </>
      }
    >
      <form id="rule-form" onSubmit={submit} className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Module</label>
            <input
              className="field"
              value={form.module}
              onChange={(e) => setForm({ ...form, module: e.target.value })}
              placeholder="ex: comptes"
              autoFocus
            />
          </div>
          <div>
            <label className="label">Type d'evenement</label>
            <input
              className="field"
              value={form.event_type}
              onChange={(e) => setForm({ ...form, event_type: e.target.value })}
              placeholder="ex: checkpoint"
            />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Seuil erreurs</label>
            <input
              type="number"
              className="field"
              value={form.threshold_errors}
              min={1}
              onChange={(e) => setForm({ ...form, threshold_errors: Number(e.target.value) })}
            />
          </div>
          <div>
            <label className="label">Seuil actions</label>
            <input
              type="number"
              className="field"
              value={form.threshold_actions}
              min={1}
              onChange={(e) => setForm({ ...form, threshold_actions: Number(e.target.value) })}
            />
          </div>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={form.tg_enabled}
            onChange={(e) => setForm({ ...form, tg_enabled: e.target.checked })}
            className="accent-accent-1"
          />
          Notifier via Telegram
        </label>
      </form>
    </Modal>
  )
}

// --- Main page ---------------------------------------------------------------

const TABS: { key: Tab; label: string }[] = [
  { key: 'live', label: 'Live' },
  { key: 'events', label: 'Historique' },
  { key: 'incidents', label: 'Incidents' },
  { key: 'rules', label: 'Regles' },
]

export default function LogsPage() {
  const [tab, setTab] = useState<Tab>('live')

  return (
    <div>
      <StatsBar />

      <div className="mb-5 flex gap-1 rounded-xl bg-white/[0.03] p-1">
        {TABS.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            className={`rounded-lg px-4 py-2 text-[13px] font-semibold transition-colors ${
              tab === key
                ? 'bg-accent-1/15 text-white'
                : 'text-muted hover:text-white'
            }`}
            onClick={() => setTab(key)}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'live' && <LiveTab />}
      {tab === 'events' && <EventsTab />}
      {tab === 'incidents' && <IncidentsTab />}
      {tab === 'rules' && <RulesTab />}
    </div>
  )
}
