import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  ArrowClockwise,
  Clock,
  FloppyDisk,
  Lightning,
  Play,
  Plus,
  Trash,
} from '@phosphor-icons/react'
import Modal from '../../components/Modal'
import { PLATFORM_META } from '../../components/PlatformBadge'
import { Empty, ErrorState, Loading } from '../../components/StateBlock'
import {
  useScenariosOverview,
  useScenariosList,
  useRuns,
  usePlages,
  useSaveScenario,
  useDeleteScenario,
  useDeleteRun,
  useSavePlage,
  useDeletePlage,
} from '../../hooks/useApi'
import { PLATFORMS, type Platform } from '../../types/compte'
import type {
  Scenario,
  ScenarioInput,
  ScenarioFilters,
  RunFilters,
  PlageHoraire,
  PlageHoraireInput,
} from '../../types/scenario'

type Tab = 'overview' | 'scenarios' | 'runs' | 'plages'

const TABS: { key: Tab; label: string }[] = [
  { key: 'overview', label: "Vue d'ensemble" },
  { key: 'scenarios', label: 'Scenarios' },
  { key: 'runs', label: 'Executions' },
  { key: 'plages', label: 'Plages horaires' },
]

const ORIGIN_LABELS: Record<string, string> = {
  spontane: 'Spontane',
  login: 'Login',
  creation: 'Creation',
}

const RUN_STATUS_LABELS: Record<string, string> = {
  pending: 'En attente',
  running: 'En cours',
  paused: 'En pause',
  done: 'Termine',
  error: 'Erreur',
}

const RUN_STATUS_COLORS: Record<string, string> = {
  pending: '#8b8fa3',
  running: '#22c55e',
  paused: '#f59e0b',
  done: '#6d5ef0',
  error: '#ef4444',
}

const DAY_LABELS = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']

// --- KPI card ----------------------------------------------------------------

function KpiCard({
  icon: Icon,
  color,
  label,
  value,
}: {
  icon: typeof Lightning
  color: string
  label: string
  value: string
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
      </div>
    </div>
  )
}

// --- Scenario Form -----------------------------------------------------------

function ScenarioForm({
  scenario,
  onClose,
}: {
  scenario?: Scenario
  onClose: () => void
}) {
  const save = useSaveScenario()
  const [form, setForm] = useState<ScenarioInput>({
    name: scenario?.name ?? '',
    origin: scenario?.origin ?? 'spontane',
    couple: scenario?.couple ?? null,
    plateforme: scenario?.plateforme ?? null,
    loop: scenario?.loop ?? false,
    active: scenario?.active ?? true,
    description: scenario?.description ?? null,
  })

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    save.mutate({ id: scenario?.id, data: form }, { onSuccess: onClose })
  }

  return (
    <Modal
      title={scenario ? `Modifier ${scenario.name}` : 'Nouveau scenario'}
      onClose={onClose}
      width={540}
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={onClose}>Annuler</button>
          <button type="submit" form="scenario-form" className="btn btn-primary" disabled={save.isPending || !form.name.trim()}>
            <FloppyDisk size={16} /> Enregistrer
          </button>
        </>
      }
    >
      <form id="scenario-form" onSubmit={submit} className="space-y-4">
        <div>
          <label className="label">Nom</label>
          <input className="field" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} autoFocus />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Origine</label>
            <select className="field" value={form.origin} onChange={(e) => setForm({ ...form, origin: e.target.value as ScenarioInput['origin'] })}>
              {Object.entries(ORIGIN_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Plateforme</label>
            <select className="field" value={form.plateforme ?? ''} onChange={(e) => setForm({ ...form, plateforme: (e.target.value || null) as Platform | null })}>
              <option value="">Toutes</option>
              {PLATFORMS.map((p) => <option key={p} value={p}>{PLATFORM_META[p].label}</option>)}
            </select>
          </div>
        </div>
        <div>
          <label className="label">Description</label>
          <textarea className="field min-h-[80px]" value={form.description ?? ''} onChange={(e) => setForm({ ...form, description: e.target.value || null })} />
        </div>
        <div className="flex gap-6">
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input type="checkbox" checked={form.loop} onChange={(e) => setForm({ ...form, loop: e.target.checked })} />
            Boucle
          </label>
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input type="checkbox" checked={form.active} onChange={(e) => setForm({ ...form, active: e.target.checked })} />
            Actif
          </label>
        </div>
      </form>
    </Modal>
  )
}

// --- Plage Form --------------------------------------------------------------

function PlageForm({
  plage,
  onClose,
}: {
  plage?: PlageHoraire
  onClose: () => void
}) {
  const save = useSavePlage()
  const [form, setForm] = useState<PlageHoraireInput>({
    name: plage?.name ?? '',
    days: plage?.days ?? [],
    ranges: plage?.ranges ?? [{ start: '08:00', end: '12:00' }],
  })

  const toggleDay = (d: number) => {
    const days = form.days ?? []
    setForm({ ...form, days: days.includes(d) ? days.filter((x) => x !== d) : [...days, d].sort() })
  }

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    save.mutate({ id: plage?.id, data: form }, { onSuccess: onClose })
  }

  return (
    <Modal
      title={plage ? `Modifier ${plage.name}` : 'Nouvelle plage'}
      onClose={onClose}
      width={480}
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={onClose}>Annuler</button>
          <button type="submit" form="plage-form" className="btn btn-primary" disabled={save.isPending || !form.name.trim()}>
            <FloppyDisk size={16} /> Enregistrer
          </button>
        </>
      }
    >
      <form id="plage-form" onSubmit={submit} className="space-y-4">
        <div>
          <label className="label">Nom</label>
          <input className="field" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} autoFocus />
        </div>
        <div>
          <label className="label">Jours</label>
          <div className="flex gap-2">
            {DAY_LABELS.map((l, i) => (
              <button
                key={i}
                type="button"
                className={`chip ${(form.days ?? []).includes(i) ? 'bg-accent-1/30 text-white' : ''}`}
                onClick={() => toggleDay(i)}
              >
                {l}
              </button>
            ))}
          </div>
        </div>
        <div>
          <label className="label">Plages</label>
          {(form.ranges ?? []).map((r, i) => (
            <div key={i} className="flex gap-2 items-center mb-2">
              <input
                type="time"
                className="field flex-1"
                value={r.start}
                onChange={(e) => {
                  const ranges = [...(form.ranges ?? [])]
                  ranges[i] = { ...ranges[i], start: e.target.value }
                  setForm({ ...form, ranges })
                }}
              />
              <span className="text-muted">a</span>
              <input
                type="time"
                className="field flex-1"
                value={r.end}
                onChange={(e) => {
                  const ranges = [...(form.ranges ?? [])]
                  ranges[i] = { ...ranges[i], end: e.target.value }
                  setForm({ ...form, ranges })
                }}
              />
              {(form.ranges ?? []).length > 1 && (
                <button type="button" className="icon-btn" onClick={() => setForm({ ...form, ranges: (form.ranges ?? []).filter((_, j) => j !== i) })}>
                  <Trash size={14} />
                </button>
              )}
            </div>
          ))}
          <button type="button" className="btn btn-ghost text-xs mt-1" onClick={() => setForm({ ...form, ranges: [...(form.ranges ?? []), { start: '14:00', end: '18:00' }] })}>
            <Plus size={12} /> Ajouter plage
          </button>
        </div>
      </form>
    </Modal>
  )
}

// --- Main Page ---------------------------------------------------------------

export default function ScenariosPage() {
  const [params, setParams] = useSearchParams()
  const tab = (params.get('tab') as Tab) || 'overview'
  const setTab = (t: Tab) => setParams({ tab: t })

  // Editing state
  const [editingScenario, setEditingScenario] = useState<Scenario | null | undefined>(undefined)
  const [editingPlage, setEditingPlage] = useState<PlageHoraire | null | undefined>(undefined)
  const [confirmDelete, setConfirmDelete] = useState<{ type: string; id: string; name: string } | null>(null)

  // Filters
  const [sFilters, setSFilters] = useState<ScenarioFilters>({})
  const [rFilters, setRFilters] = useState<RunFilters>({})

  // Data
  const overview = useScenariosOverview()
  const scenarios = useScenariosList(sFilters)
  const runs = useRuns(rFilters)
  const plages = usePlages()
  const deleteScenario = useDeleteScenario()
  const deleteRun = useDeleteRun()
  const deletePlage = useDeletePlage()

  const handleDelete = () => {
    if (!confirmDelete) return
    const { type, id } = confirmDelete
    const mutation = type === 'scenario' ? deleteScenario : type === 'run' ? deleteRun : deletePlage
    mutation.mutate(id, { onSuccess: () => setConfirmDelete(null) })
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Scenarios</h1>
        {tab === 'scenarios' && (
          <button className="btn btn-primary" onClick={() => setEditingScenario(null)}>
            <Plus size={16} /> Nouveau
          </button>
        )}
        {tab === 'plages' && (
          <button className="btn btn-primary" onClick={() => setEditingPlage(null)}>
            <Plus size={16} /> Nouvelle plage
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-white/[0.06] pb-px">
        {TABS.map((t) => (
          <button
            key={t.key}
            className={`px-4 py-2 text-sm rounded-t-lg transition-colors ${tab === t.key ? 'bg-white/[0.06] text-white' : 'text-muted hover:text-white'}`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Overview */}
      {tab === 'overview' && (
        overview.isLoading ? <Loading /> :
        overview.error ? <ErrorState error={overview.error} onRetry={overview.refetch} /> :
        overview.data && (
          <div className="grid grid-cols-5 gap-4">
            <KpiCard icon={Lightning} color="#6d5ef0" label="Scenarios" value={String(overview.data.total_scenarios)} />
            <KpiCard icon={Play} color="#22c55e" label="Actifs" value={String(overview.data.active_scenarios)} />
            <KpiCard icon={ArrowClockwise} color="#4b7bf5" label="Total runs" value={String(overview.data.total_runs)} />
            <KpiCard icon={Play} color="#f59e0b" label="En cours" value={String(overview.data.running_now)} />
            <KpiCard icon={Clock} color="#8b8fa3" label="Plages" value={String(overview.data.total_plages)} />
          </div>
        )
      )}

      {/* Scenarios list */}
      {tab === 'scenarios' && (
        <>
          <div className="flex gap-3">
            <select className="field w-40" value={sFilters.origin ?? ''} onChange={(e) => setSFilters({ ...sFilters, origin: e.target.value || undefined })}>
              <option value="">Toute origine</option>
              {Object.entries(ORIGIN_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            <select className="field w-40" value={sFilters.plateforme ?? ''} onChange={(e) => setSFilters({ ...sFilters, plateforme: e.target.value || undefined })}>
              <option value="">Toute plateforme</option>
              {PLATFORMS.map((p) => <option key={p} value={p}>{PLATFORM_META[p].label}</option>)}
            </select>
          </div>

          {scenarios.isLoading ? <Loading /> :
           scenarios.error ? <ErrorState error={scenarios.error} onRetry={scenarios.refetch} /> :
           !scenarios.data?.length ? <Empty>Aucun scenario</Empty> : (
            <div className="card overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/[0.06] text-left text-muted">
                    <th className="px-4 py-3 font-medium">Nom</th>
                    <th className="px-4 py-3 font-medium">Origine</th>
                    <th className="px-4 py-3 font-medium">Plateforme</th>
                    <th className="px-4 py-3 font-medium">Boucle</th>
                    <th className="px-4 py-3 font-medium">Actif</th>
                    <th className="px-4 py-3 font-medium">Steps</th>
                    <th className="px-4 py-3 font-medium w-20"></th>
                  </tr>
                </thead>
                <tbody>
                  {scenarios.data.map((s) => (
                    <tr key={s.id} className="border-b border-white/[0.04] hover:bg-white/[0.02] cursor-pointer" onClick={() => setEditingScenario(s)}>
                      <td className="px-4 py-3 font-medium">{s.name}</td>
                      <td className="px-4 py-3"><span className="chip">{ORIGIN_LABELS[s.origin] ?? s.origin}</span></td>
                      <td className="px-4 py-3">{s.plateforme ? PLATFORM_META[s.plateforme as Platform]?.label : '—'}</td>
                      <td className="px-4 py-3">{s.loop ? <ArrowClockwise size={16} className="text-accent-1" /> : '—'}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-block h-2 w-2 rounded-full ${s.active ? 'bg-green-500' : 'bg-gray-500'}`} />
                      </td>
                      <td className="px-4 py-3 tabular-nums">{s.steps?.length ?? 0}</td>
                      <td className="px-4 py-3 text-right">
                        <button className="icon-btn" onClick={(e) => { e.stopPropagation(); setConfirmDelete({ type: 'scenario', id: s.id, name: s.name }) }}>
                          <Trash size={14} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* Runs list */}
      {tab === 'runs' && (
        <>
          <div className="flex gap-3">
            <select className="field w-40" value={rFilters.status ?? ''} onChange={(e) => setRFilters({ ...rFilters, status: e.target.value || undefined })}>
              <option value="">Tout statut</option>
              {Object.entries(RUN_STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>

          {runs.isLoading ? <Loading /> :
           runs.error ? <ErrorState error={runs.error} onRetry={runs.refetch} /> :
           !runs.data?.length ? <Empty>Aucune execution</Empty> : (
            <div className="card overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/[0.06] text-left text-muted">
                    <th className="px-4 py-3 font-medium">ID</th>
                    <th className="px-4 py-3 font-medium">Statut</th>
                    <th className="px-4 py-3 font-medium">Etape</th>
                    <th className="px-4 py-3 font-medium">Comptes</th>
                    <th className="px-4 py-3 font-medium">Demarre</th>
                    <th className="px-4 py-3 font-medium w-20"></th>
                  </tr>
                </thead>
                <tbody>
                  {runs.data.map((r) => (
                    <tr key={r.id} className="border-b border-white/[0.04] hover:bg-white/[0.02]">
                      <td className="px-4 py-3 font-mono text-xs">{r.id.slice(0, 8)}</td>
                      <td className="px-4 py-3">
                        <span className="chip" style={{ background: `${RUN_STATUS_COLORS[r.status]}20`, color: RUN_STATUS_COLORS[r.status] }}>
                          {RUN_STATUS_LABELS[r.status] ?? r.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 tabular-nums">{r.current_step}</td>
                      <td className="px-4 py-3 tabular-nums">{r.comptes?.length ?? 0}</td>
                      <td className="px-4 py-3 text-muted">{r.started_at ? new Date(r.started_at).toLocaleString('fr-FR') : '—'}</td>
                      <td className="px-4 py-3 text-right">
                        <button className="icon-btn" onClick={() => setConfirmDelete({ type: 'run', id: r.id, name: r.id.slice(0, 8) })}>
                          <Trash size={14} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* Plages list */}
      {tab === 'plages' && (
        plages.isLoading ? <Loading /> :
        plages.error ? <ErrorState error={plages.error} onRetry={plages.refetch} /> :
        !plages.data?.length ? <Empty>Aucune plage horaire</Empty> : (
          <div className="grid grid-cols-3 gap-4">
            {plages.data.map((p) => (
              <div key={p.id} className="card px-5 py-4 cursor-pointer hover:bg-white/[0.02]" onClick={() => setEditingPlage(p)}>
                <div className="flex items-center justify-between mb-3">
                  <div className="font-medium">{p.name}</div>
                  <button className="icon-btn" onClick={(e) => { e.stopPropagation(); setConfirmDelete({ type: 'plage', id: p.id, name: p.name }) }}>
                    <Trash size={14} />
                  </button>
                </div>
                <div className="flex gap-1 mb-2">
                  {DAY_LABELS.map((l, i) => (
                    <span key={i} className={`text-[10px] px-1.5 py-0.5 rounded ${(p.days ?? []).includes(i) ? 'bg-accent-1/30 text-white' : 'text-dim'}`}>
                      {l}
                    </span>
                  ))}
                </div>
                <div className="text-xs text-muted">
                  {(p.ranges ?? []).map((r, i) => <span key={i}>{r.start} – {r.end}{i < (p.ranges ?? []).length - 1 ? ', ' : ''}</span>)}
                </div>
              </div>
            ))}
          </div>
        )
      )}

      {/* Modals */}
      {editingScenario !== undefined && (
        <ScenarioForm scenario={editingScenario ?? undefined} onClose={() => setEditingScenario(undefined)} />
      )}
      {editingPlage !== undefined && (
        <PlageForm plage={editingPlage ?? undefined} onClose={() => setEditingPlage(undefined)} />
      )}
      {confirmDelete && (
        <Modal title="Confirmer la suppression" onClose={() => setConfirmDelete(null)} width={400} footer={
          <>
            <button className="btn btn-ghost" onClick={() => setConfirmDelete(null)}>Annuler</button>
            <button className="btn btn-danger" onClick={handleDelete}>Supprimer</button>
          </>
        }>
          <p>Supprimer <strong>{confirmDelete.name}</strong> ?</p>
        </Modal>
      )}
    </div>
  )
}
