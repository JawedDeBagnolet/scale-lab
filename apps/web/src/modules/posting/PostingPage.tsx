import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  CalendarBlank,
  Check,
  Clock,
  FloppyDisk,
  FolderOpen,
  Image,
  MegaphoneSimple,
  Plus,
  Trash,
  Warning,
} from '@phosphor-icons/react'
import Modal from '../../components/Modal'
import { PLATFORM_META } from '../../components/PlatformBadge'
import { Empty, ErrorState, Loading } from '../../components/StateBlock'
import {
  usePostingOverview,
  useCollections,
  usePostingMedias,
  useCampagnes,
  usePublications,
  useSaveCollection,
  useDeleteCollection,
  useSaveCampagne,
  useDeleteCampagne,
  useDeletePublication,
  usePersonas,
} from '../../hooks/useApi'
import { PLATFORMS, type Platform } from '../../types/compte'
import type {
  Collection,
  CollectionInput,
  CollectionFilters,
  Campagne,
  CampagneInput,
  CampagneFilters,
  PublicationFilters,
} from '../../types/posting'

type Tab = 'overview' | 'collections' | 'medias' | 'campagnes' | 'publications'

const TABS: { key: Tab; label: string }[] = [
  { key: 'overview', label: "Vue d'ensemble" },
  { key: 'collections', label: 'Collections' },
  { key: 'medias', label: 'Medias' },
  { key: 'campagnes', label: 'Campagnes' },
  { key: 'publications', label: 'Publications' },
]

const CAMPAGNE_STATUS_LABELS: Record<string, string> = {
  draft: 'Brouillon',
  active: 'Active',
  paused: 'En pause',
  done: 'Terminee',
}

const CAMPAGNE_STATUS_COLORS: Record<string, string> = {
  draft: '#8b8fa3',
  active: '#22c55e',
  paused: '#f59e0b',
  done: '#6d5ef0',
}

const PUB_STATUS_LABELS: Record<string, string> = {
  planned: 'Planifiee',
  published: 'Publiee',
  failed: 'Echec',
  suspended: 'Suspendue',
}

const PUB_STATUS_COLORS: Record<string, string> = {
  planned: '#4b7bf5',
  published: '#22c55e',
  failed: '#ef4444',
  suspended: '#f59e0b',
}

const COLLECTION_TYPE_LABELS: Record<string, string> = {
  assembled: 'Assemble',
  variable: 'Variable',
}

// --- KPI card ----------------------------------------------------------------

function KpiCard({
  icon: Icon,
  color,
  label,
  value,
  sub,
}: {
  icon: typeof MegaphoneSimple
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

// --- Collection Form ---------------------------------------------------------

function CollectionForm({
  collection,
  onClose,
}: {
  collection?: Collection
  onClose: () => void
}) {
  const save = useSaveCollection()
  const personas = usePersonas()
  const [form, setForm] = useState<CollectionInput>({
    name: collection?.name ?? '',
    collection_type: collection?.collection_type ?? 'assembled',
    persona_id: collection?.persona_id ?? null,
    plateforme: collection?.plateforme ?? null,
    post_type: collection?.post_type ?? 'post',
  })

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    save.mutate({ id: collection?.id, data: form }, { onSuccess: onClose })
  }

  return (
    <Modal
      title={collection ? `Modifier ${collection.name}` : 'Nouvelle collection'}
      onClose={onClose}
      width={500}
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={onClose}>Annuler</button>
          <button type="submit" form="coll-form" className="btn btn-primary" disabled={save.isPending || !form.name.trim()}>
            <FloppyDisk size={16} /> Enregistrer
          </button>
        </>
      }
    >
      <form id="coll-form" onSubmit={submit} className="space-y-4">
        <div>
          <label className="label">Nom</label>
          <input className="field" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} autoFocus />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Type</label>
            <select className="field" value={form.collection_type} onChange={(e) => setForm({ ...form, collection_type: e.target.value as CollectionInput['collection_type'] })}>
              {Object.entries(COLLECTION_TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Type de post</label>
            <select className="field" value={form.post_type ?? ''} onChange={(e) => setForm({ ...form, post_type: e.target.value || null })}>
              <option value="post">Post</option>
              <option value="story">Story</option>
              <option value="reel">Reel</option>
            </select>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Persona</label>
            <select className="field" value={form.persona_id ?? ''} onChange={(e) => setForm({ ...form, persona_id: e.target.value || null })}>
              <option value="">Aucune</option>
              {personas.data?.map((p) => <option key={p.id} value={p.id}>{p.first_name} {p.last_name}</option>)}
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
      </form>
    </Modal>
  )
}

// --- Campagne Form -----------------------------------------------------------

function CampagneForm({
  campagne,
  onClose,
}: {
  campagne?: Campagne
  onClose: () => void
}) {
  const save = useSaveCampagne()
  const personas = usePersonas()
  const [form, setForm] = useState<CampagneInput>({
    name: campagne?.name ?? '',
    persona_id: campagne?.persona_id ?? null,
    plateforme: campagne?.plateforme ?? null,
    status: campagne?.status ?? 'draft',
  })

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    save.mutate({ id: campagne?.id, data: form }, { onSuccess: onClose })
  }

  return (
    <Modal
      title={campagne ? `Modifier ${campagne.name}` : 'Nouvelle campagne'}
      onClose={onClose}
      width={500}
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={onClose}>Annuler</button>
          <button type="submit" form="camp-form" className="btn btn-primary" disabled={save.isPending || !form.name.trim()}>
            <FloppyDisk size={16} /> Enregistrer
          </button>
        </>
      }
    >
      <form id="camp-form" onSubmit={submit} className="space-y-4">
        <div>
          <label className="label">Nom</label>
          <input className="field" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} autoFocus />
        </div>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="label">Persona</label>
            <select className="field" value={form.persona_id ?? ''} onChange={(e) => setForm({ ...form, persona_id: e.target.value || null })}>
              <option value="">Aucune</option>
              {personas.data?.map((p) => <option key={p.id} value={p.id}>{p.first_name} {p.last_name}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Plateforme</label>
            <select className="field" value={form.plateforme ?? ''} onChange={(e) => setForm({ ...form, plateforme: (e.target.value || null) as Platform | null })}>
              <option value="">Toutes</option>
              {PLATFORMS.map((p) => <option key={p} value={p}>{PLATFORM_META[p].label}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Statut</label>
            <select className="field" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value as CampagneInput['status'] })}>
              {Object.entries(CAMPAGNE_STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
        </div>
      </form>
    </Modal>
  )
}

// --- Main Page ---------------------------------------------------------------

export default function PostingPage() {
  const [params, setParams] = useSearchParams()
  const tab = (params.get('tab') as Tab) || 'overview'
  const setTab = (t: Tab) => setParams({ tab: t })

  const [editingCollection, setEditingCollection] = useState<Collection | null | undefined>(undefined)
  const [editingCampagne, setEditingCampagne] = useState<Campagne | null | undefined>(undefined)
  const [confirmDelete, setConfirmDelete] = useState<{ type: string; id: string; name: string } | null>(null)

  const [cFilters, setCFilters] = useState<CollectionFilters>({})
  const [campFilters, setCampFilters] = useState<CampagneFilters>({})
  const [pubFilters, setPubFilters] = useState<PublicationFilters>({})

  const overview = usePostingOverview()
  const collections = useCollections(cFilters)
  const medias = usePostingMedias({})
  const campagnes = useCampagnes(campFilters)
  const publications = usePublications(pubFilters)
  const deleteCollection = useDeleteCollection()
  const deleteCampagne = useDeleteCampagne()
  const deletePublication = useDeletePublication()

  const handleDelete = () => {
    if (!confirmDelete) return
    const { type, id } = confirmDelete
    const mutation = type === 'collection' ? deleteCollection : type === 'campagne' ? deleteCampagne : deletePublication
    mutation.mutate(id, { onSuccess: () => setConfirmDelete(null) })
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Posting</h1>
        {tab === 'collections' && (
          <button className="btn btn-primary" onClick={() => setEditingCollection(null)}>
            <Plus size={16} /> Nouvelle collection
          </button>
        )}
        {tab === 'campagnes' && (
          <button className="btn btn-primary" onClick={() => setEditingCampagne(null)}>
            <Plus size={16} /> Nouvelle campagne
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
          <div className="space-y-4">
            <div className="grid grid-cols-4 gap-4">
              <KpiCard icon={FolderOpen} color="#6d5ef0" label="Collections" value={String(overview.data.total_collections)} />
              <KpiCard icon={Image} color="#4b7bf5" label="Medias" value={String(overview.data.total_medias)} />
              <KpiCard icon={MegaphoneSimple} color="#22c55e" label="Campagnes" value={String(overview.data.total_campagnes)} sub={`${overview.data.active_campagnes} actives`} />
              <KpiCard icon={CalendarBlank} color="#f59e0b" label="Publications" value={String(overview.data.total_publications)} />
            </div>
            <div className="grid grid-cols-3 gap-4">
              <KpiCard icon={Clock} color="#4b7bf5" label="Planifiees" value={String(overview.data.planned)} />
              <KpiCard icon={Check} color="#22c55e" label="Publiees" value={String(overview.data.published)} />
              <KpiCard icon={Warning} color="#ef4444" label="Echec" value={String(overview.data.failed)} />
            </div>
          </div>
        )
      )}

      {/* Collections */}
      {tab === 'collections' && (
        <>
          <div className="flex gap-3">
            <select className="field w-40" value={cFilters.collection_type ?? ''} onChange={(e) => setCFilters({ ...cFilters, collection_type: e.target.value || undefined })}>
              <option value="">Tout type</option>
              {Object.entries(COLLECTION_TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            <select className="field w-40" value={cFilters.plateforme ?? ''} onChange={(e) => setCFilters({ ...cFilters, plateforme: e.target.value || undefined })}>
              <option value="">Toute plateforme</option>
              {PLATFORMS.map((p) => <option key={p} value={p}>{PLATFORM_META[p].label}</option>)}
            </select>
          </div>

          {collections.isLoading ? <Loading /> :
           collections.error ? <ErrorState error={collections.error} onRetry={collections.refetch} /> :
           !collections.data?.length ? <Empty>Aucune collection</Empty> : (
            <div className="card overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/[0.06] text-left text-muted">
                    <th className="px-4 py-3 font-medium">Nom</th>
                    <th className="px-4 py-3 font-medium">Type</th>
                    <th className="px-4 py-3 font-medium">Plateforme</th>
                    <th className="px-4 py-3 font-medium">Post type</th>
                    <th className="px-4 py-3 font-medium">Medias</th>
                    <th className="px-4 py-3 font-medium w-20"></th>
                  </tr>
                </thead>
                <tbody>
                  {collections.data.map((c) => (
                    <tr key={c.id} className="border-b border-white/[0.04] hover:bg-white/[0.02] cursor-pointer" onClick={() => setEditingCollection(c)}>
                      <td className="px-4 py-3 font-medium">{c.name}</td>
                      <td className="px-4 py-3"><span className="chip">{COLLECTION_TYPE_LABELS[c.collection_type] ?? c.collection_type}</span></td>
                      <td className="px-4 py-3">{c.plateforme ? PLATFORM_META[c.plateforme as Platform]?.label : '—'}</td>
                      <td className="px-4 py-3">{c.post_type ?? '—'}</td>
                      <td className="px-4 py-3 tabular-nums">{c.media_ids?.length ?? 0}</td>
                      <td className="px-4 py-3 text-right">
                        <button className="icon-btn" onClick={(e) => { e.stopPropagation(); setConfirmDelete({ type: 'collection', id: c.id, name: c.name }) }}>
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

      {/* Medias */}
      {tab === 'medias' && (
        medias.isLoading ? <Loading /> :
        medias.error ? <ErrorState error={medias.error} onRetry={medias.refetch} /> :
        !medias.data?.length ? <Empty>Aucun media</Empty> : (
          <div className="grid grid-cols-4 gap-4">
            {medias.data.map((m) => (
              <div key={m.id} className="card px-4 py-3">
                <div className="flex items-center gap-2 mb-2">
                  <Image size={16} className="text-muted" />
                  <span className="chip text-xs">{m.media_type}</span>
                  {m.used && <span className="chip text-xs bg-green-500/20 text-green-400">Utilise</span>}
                </div>
                <div className="text-xs text-muted truncate">{m.url}</div>
                {m.folder && <div className="text-xs text-dim mt-1">{m.folder}</div>}
                {m.duration != null && <div className="text-xs text-dim">{m.duration}s</div>}
              </div>
            ))}
          </div>
        )
      )}

      {/* Campagnes */}
      {tab === 'campagnes' && (
        <>
          <div className="flex gap-3">
            <select className="field w-40" value={campFilters.status ?? ''} onChange={(e) => setCampFilters({ ...campFilters, status: e.target.value || undefined })}>
              <option value="">Tout statut</option>
              {Object.entries(CAMPAGNE_STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            <select className="field w-40" value={campFilters.plateforme ?? ''} onChange={(e) => setCampFilters({ ...campFilters, plateforme: e.target.value || undefined })}>
              <option value="">Toute plateforme</option>
              {PLATFORMS.map((p) => <option key={p} value={p}>{PLATFORM_META[p].label}</option>)}
            </select>
          </div>

          {campagnes.isLoading ? <Loading /> :
           campagnes.error ? <ErrorState error={campagnes.error} onRetry={campagnes.refetch} /> :
           !campagnes.data?.length ? <Empty>Aucune campagne</Empty> : (
            <div className="card overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/[0.06] text-left text-muted">
                    <th className="px-4 py-3 font-medium">Nom</th>
                    <th className="px-4 py-3 font-medium">Statut</th>
                    <th className="px-4 py-3 font-medium">Plateforme</th>
                    <th className="px-4 py-3 font-medium">Cree le</th>
                    <th className="px-4 py-3 font-medium w-20"></th>
                  </tr>
                </thead>
                <tbody>
                  {campagnes.data.map((c) => (
                    <tr key={c.id} className="border-b border-white/[0.04] hover:bg-white/[0.02] cursor-pointer" onClick={() => setEditingCampagne(c)}>
                      <td className="px-4 py-3 font-medium">{c.name}</td>
                      <td className="px-4 py-3">
                        <span className="chip" style={{ background: `${CAMPAGNE_STATUS_COLORS[c.status]}20`, color: CAMPAGNE_STATUS_COLORS[c.status] }}>
                          {CAMPAGNE_STATUS_LABELS[c.status] ?? c.status}
                        </span>
                      </td>
                      <td className="px-4 py-3">{c.plateforme ? PLATFORM_META[c.plateforme as Platform]?.label : '—'}</td>
                      <td className="px-4 py-3 text-muted">{new Date(c.created_at).toLocaleDateString('fr-FR')}</td>
                      <td className="px-4 py-3 text-right">
                        <button className="icon-btn" onClick={(e) => { e.stopPropagation(); setConfirmDelete({ type: 'campagne', id: c.id, name: c.name }) }}>
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

      {/* Publications */}
      {tab === 'publications' && (
        <>
          <div className="flex gap-3">
            <select className="field w-40" value={pubFilters.status ?? ''} onChange={(e) => setPubFilters({ ...pubFilters, status: e.target.value || undefined })}>
              <option value="">Tout statut</option>
              {Object.entries(PUB_STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>

          {publications.isLoading ? <Loading /> :
           publications.error ? <ErrorState error={publications.error} onRetry={publications.refetch} /> :
           !publications.data?.length ? <Empty>Aucune publication</Empty> : (
            <div className="card overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/[0.06] text-left text-muted">
                    <th className="px-4 py-3 font-medium">ID</th>
                    <th className="px-4 py-3 font-medium">Statut</th>
                    <th className="px-4 py-3 font-medium">Planifiee</th>
                    <th className="px-4 py-3 font-medium">Caption</th>
                    <th className="px-4 py-3 font-medium w-20"></th>
                  </tr>
                </thead>
                <tbody>
                  {publications.data.map((p) => (
                    <tr key={p.id} className="border-b border-white/[0.04] hover:bg-white/[0.02]">
                      <td className="px-4 py-3 font-mono text-xs">{p.id.slice(0, 8)}</td>
                      <td className="px-4 py-3">
                        <span className="chip" style={{ background: `${PUB_STATUS_COLORS[p.status]}20`, color: PUB_STATUS_COLORS[p.status] }}>
                          {PUB_STATUS_LABELS[p.status] ?? p.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-muted">{p.scheduled_at ? new Date(p.scheduled_at).toLocaleString('fr-FR') : '—'}</td>
                      <td className="px-4 py-3 text-muted truncate max-w-[300px]">{p.caption ?? '—'}</td>
                      <td className="px-4 py-3 text-right">
                        <button className="icon-btn" onClick={() => setConfirmDelete({ type: 'publication', id: p.id, name: p.id.slice(0, 8) })}>
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

      {/* Modals */}
      {editingCollection !== undefined && (
        <CollectionForm collection={editingCollection ?? undefined} onClose={() => setEditingCollection(undefined)} />
      )}
      {editingCampagne !== undefined && (
        <CampagneForm campagne={editingCampagne ?? undefined} onClose={() => setEditingCampagne(undefined)} />
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
