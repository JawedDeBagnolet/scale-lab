import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  Binoculars,
  FloppyDisk,
  FolderSimple,
  Image,
  PencilSimple,
  Plus,
  Star,
  Target,
  Trash,
  VideoCamera,
  XCircle,
} from '@phosphor-icons/react'
import ConfirmDialog from '../../components/ConfirmDialog'
import Modal from '../../components/Modal'
import PlatformBadge, { PLATFORM_META } from '../../components/PlatformBadge'
import { Empty, ErrorState, Loading } from '../../components/StateBlock'
import {
  useAddFavorite,
  useAlbums,
  useDeleteAlbum,
  useDeleteSource,
  useFavorites,
  useInspirations,
  useNiches,
  usePersonas,
  useSaveAlbum,
  useSaveSnipe,
  useSaveSource,
  useSnipes,
  useUpdateInspiration,
  useVeilleOverview,
  useVeilleSources,
} from '../../hooks/useApi'
import { PLATFORMS, type Platform } from '../../types/compte'
import {
  INSPIRATION_STATUSES,
  MEDIA_TYPES,
  SNIPE_PRIORITIES,
  SNIPE_STATUSES,
  type Album,
  type AlbumInput,
  type Inspiration,
  type InspirationStatus,
  type MediaType,
  type SnipePriority,
  type SnipeStatus,
  type VeilleSource,
  type VeilleSourceInput,
} from '../../types/veille'

type Tab = 'sources' | 'inspirations' | 'snipes' | 'albums'

const isPlatform = (v: string | null): v is Platform => PLATFORMS.includes(v as Platform)

const PRIORITY_COLORS: Record<SnipePriority, string> = {
  low: '#8b8fa3',
  medium: '#f59e0b',
  high: '#ef4444',
}

const PRIORITY_LABELS: Record<SnipePriority, string> = {
  low: 'Basse',
  medium: 'Moyenne',
  high: 'Haute',
}

const SNIPE_STATUS_LABELS: Record<SnipeStatus, string> = {
  pending: 'En attente',
  in_progress: 'En cours',
  done: 'Termine',
  cancelled: 'Annule',
}

const INSPIRATION_STATUS_LABELS: Record<InspirationStatus, string> = {
  new: 'Nouveau',
  reviewed: 'Vu',
  used: 'Utilise',
  dismissed: 'Ecarte',
}

const MEDIA_TYPE_LABELS: Record<MediaType, string> = {
  image: 'Image',
  video: 'Video',
  reel: 'Reel',
}

// --- KPI bar ---------------------------------------------------------------

function KpiBar() {
  const overview = useVeilleOverview()
  if (!overview.data) return null

  const items = [
    { label: 'Sources', value: overview.data.total_sources, color: 'var(--accent-2)', icon: Binoculars },
    { label: 'Nouvelles inspirations', value: overview.data.new_inspirations, color: 'var(--accent-1)', icon: Image },
    { label: 'Snipes en attente', value: overview.data.pending_snipes, color: 'var(--warning)', icon: Target },
    { label: 'Albums', value: overview.data.total_albums, color: 'var(--success)', icon: FolderSimple },
  ]

  return (
    <div className="mb-6 grid grid-cols-4 gap-4">
      {items.map(({ label, value, color, icon: Icon }) => (
        <div key={label} className="card flex items-center gap-4 px-5 py-4">
          <div
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl"
            style={{ background: `${color}20` }}
          >
            <Icon size={20} style={{ color }} />
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

// --- Source form modal ------------------------------------------------------

function SourceForm({ source, onClose }: { source?: VeilleSource; onClose: () => void }) {
  const save = useSaveSource()
  const niches = useNiches()

  const [form, setForm] = useState<VeilleSourceInput>({
    handle: source?.handle ?? '',
    plateforme: source?.plateforme as Platform ?? 'ig',
    niche_id: source?.niche_id ?? null,
    active: source?.active ?? true,
  })

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    save.mutate({ id: source?.id, data: form }, { onSuccess: onClose })
  }

  return (
    <Modal
      title={source ? `Modifier @${source.handle}` : 'Ajouter une source'}
      onClose={onClose}
      width={480}
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Annuler
          </button>
          <button
            type="submit"
            form="source-form"
            className="btn btn-primary"
            disabled={save.isPending || !form.handle.trim()}
          >
            <FloppyDisk size={16} /> Enregistrer
          </button>
        </>
      }
    >
      <form id="source-form" onSubmit={submit} className="space-y-4">
        <div>
          <label className="label">Handle</label>
          <input
            className="field"
            placeholder="username"
            value={form.handle}
            onChange={(e) => setForm({ ...form, handle: e.target.value })}
            autoFocus
          />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Plateforme</label>
            <select
              className="field"
              value={form.plateforme}
              onChange={(e) => setForm({ ...form, plateforme: e.target.value as Platform })}
            >
              {PLATFORMS.map((p) => (
                <option key={p} value={p}>
                  {PLATFORM_META[p].label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">Niche</label>
            <select
              className="field"
              value={form.niche_id ?? ''}
              onChange={(e) =>
                setForm({ ...form, niche_id: e.target.value ? Number(e.target.value) : null })
              }
            >
              <option value="">Aucune</option>
              {niches.data?.map((n) => (
                <option key={n.id} value={n.id}>
                  {n.label}
                </option>
              ))}
            </select>
          </div>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={form.active}
            onChange={(e) => setForm({ ...form, active: e.target.checked })}
            className="accent-accent-1"
          />
          Source active
        </label>
      </form>
    </Modal>
  )
}

// --- Sources tab -----------------------------------------------------------

function SourcesTab() {
  const [params, setParams] = useSearchParams()
  const plat = params.get('plat')
  const plateforme = isPlatform(plat) ? plat : undefined
  const niches = useNiches()
  const sources = useVeilleSources({ plateforme })
  const del = useDeleteSource()

  const [editing, setEditing] = useState<VeilleSource | null | undefined>(undefined)
  const [deleting, setDeleting] = useState<VeilleSource | null>(null)

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }

  const nicheLabels = useMemo(
    () => new Map(niches.data?.map((n) => [n.id, n.label]) ?? []),
    [niches.data],
  )

  return (
    <div>
      <div className="mb-4 flex items-center gap-3">
        <select
          className="field w-48"
          aria-label="Filtrer par plateforme"
          value={plateforme ?? ''}
          onChange={(e) => setFilter('plat', e.target.value)}
        >
          <option value="">Toutes les plateformes</option>
          {PLATFORMS.map((p) => (
            <option key={p} value={p}>
              {PLATFORM_META[p].label}
            </option>
          ))}
        </select>
        <span className="text-xs text-muted">
          {sources.data ? `${sources.data.length} source${sources.data.length > 1 ? 's' : ''}` : ''}
        </span>
        <div className="ml-auto">
          <button type="button" className="btn btn-primary" onClick={() => setEditing(null)}>
            <Plus size={16} weight="bold" /> Nouvelle source
          </button>
        </div>
      </div>

      {sources.isLoading && <Loading />}
      {sources.isError && <ErrorState error={sources.error} onRetry={() => sources.refetch()} />}
      {sources.data?.length === 0 && (
        <Empty>
          {plateforme
            ? 'Aucune source ne correspond aux filtres.'
            : 'Aucune source de veille pour le moment.'}
        </Empty>
      )}

      {sources.data && sources.data.length > 0 && (
        <div className="card overflow-hidden">
          <table className="w-full text-left text-[13px]">
            <thead>
              <tr className="border-b border-line text-[11px] uppercase tracking-wider text-muted">
                <th className="px-5 py-3 font-semibold">Handle</th>
                <th className="px-5 py-3 font-semibold">Plateforme</th>
                <th className="px-5 py-3 font-semibold">Niche</th>
                <th className="px-5 py-3 font-semibold">Active</th>
                <th className="px-5 py-3 font-semibold">Dernier scan</th>
                <th className="w-24 px-5 py-3" />
              </tr>
            </thead>
            <tbody>
              {sources.data.map((s) => (
                <tr
                  key={s.id}
                  className="border-b border-line last:border-0 hover:bg-white/[0.02]"
                >
                  <td className="px-5 py-3 font-semibold">@{s.handle}</td>
                  <td className="px-5 py-3">
                    <PlatformBadge platform={s.plateforme as Platform} withLabel />
                  </td>
                  <td className="px-5 py-3 text-muted">
                    {s.niche_id ? nicheLabels.get(s.niche_id) ?? `#${s.niche_id}` : '—'}
                  </td>
                  <td className="px-5 py-3">
                    <span className="inline-flex items-center gap-2">
                      <span
                        className="h-2 w-2 rounded-full"
                        style={{ background: s.active ? '#22c55e' : '#8b8fa3' }}
                      />
                      {s.active ? 'Oui' : 'Non'}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-muted">
                    {s.last_checked
                      ? new Date(s.last_checked).toLocaleString('fr-FR', {
                          day: '2-digit',
                          month: '2-digit',
                          hour: '2-digit',
                          minute: '2-digit',
                        })
                      : '—'}
                  </td>
                  <td className="px-5 py-3">
                    <div className="flex justify-end gap-1">
                      <button
                        type="button"
                        className="icon-btn"
                        aria-label={`Modifier @${s.handle}`}
                        onClick={() => setEditing(s)}
                      >
                        <PencilSimple size={16} />
                      </button>
                      <button
                        type="button"
                        className="icon-btn"
                        aria-label={`Supprimer @${s.handle}`}
                        onClick={() => setDeleting(s)}
                      >
                        <Trash size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {editing !== undefined && (
        <SourceForm source={editing ?? undefined} onClose={() => setEditing(undefined)} />
      )}

      {deleting && (
        <ConfirmDialog
          title="Supprimer la source"
          message={`La source @${deleting.handle} sera supprimee definitivement.`}
          pending={del.isPending}
          onCancel={() => setDeleting(null)}
          onConfirm={() => del.mutate(deleting.id, { onSuccess: () => setDeleting(null) })}
        />
      )}
    </div>
  )
}

// --- Inspirations tab ------------------------------------------------------

function InspirationsTab() {
  const [statusFilter, setStatusFilter] = useState<InspirationStatus | ''>('')
  const [mediaFilter, setMediaFilter] = useState<MediaType | ''>('')
  const inspirations = useInspirations({
    status: statusFilter || undefined,
    media_type: mediaFilter || undefined,
  })
  const update = useUpdateInspiration()
  const addFav = useAddFavorite()
  const createSnipe = useSaveSnipe()

  const handleAction = (insp: Inspiration, action: 'favorite' | 'snipe' | 'dismiss') => {
    if (action === 'favorite') {
      addFav.mutate({ inspiration_id: insp.id, album_id: null, notes: null })
      if (insp.status === 'new') {
        update.mutate({ id: insp.id, data: { status: 'reviewed' } })
      }
    } else if (action === 'snipe') {
      createSnipe.mutate({
        data: {
          inspiration_id: insp.id,
          target_persona_id: null,
          priority: 'medium',
          status: 'pending',
          due_date: null,
        },
      })
      if (insp.status === 'new') {
        update.mutate({ id: insp.id, data: { status: 'reviewed' } })
      }
    } else if (action === 'dismiss') {
      update.mutate({ id: insp.id, data: { status: 'dismissed' } })
    }
  }

  return (
    <div>
      <div className="mb-4 flex items-center gap-3">
        <select
          className="field w-44"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as InspirationStatus | '')}
        >
          <option value="">Tous les statuts</option>
          {INSPIRATION_STATUSES.map((s) => (
            <option key={s} value={s}>
              {INSPIRATION_STATUS_LABELS[s]}
            </option>
          ))}
        </select>
        <select
          className="field w-36"
          value={mediaFilter}
          onChange={(e) => setMediaFilter(e.target.value as MediaType | '')}
        >
          <option value="">Tous les types</option>
          {MEDIA_TYPES.map((t) => (
            <option key={t} value={t}>
              {MEDIA_TYPE_LABELS[t]}
            </option>
          ))}
        </select>
        <span className="text-xs text-muted">
          {inspirations.data
            ? `${inspirations.data.length} inspiration${inspirations.data.length > 1 ? 's' : ''}`
            : ''}
        </span>
      </div>

      {inspirations.isLoading && <Loading />}
      {inspirations.isError && (
        <ErrorState error={inspirations.error} onRetry={() => inspirations.refetch()} />
      )}
      {inspirations.data?.length === 0 && (
        <Empty>Aucune inspiration pour le moment.</Empty>
      )}

      {inspirations.data && inspirations.data.length > 0 && (
        <div className="grid grid-cols-3 gap-4">
          {inspirations.data.map((insp) => (
            <div key={insp.id} className="card flex flex-col overflow-hidden">
              <div className="flex h-40 items-center justify-center bg-white/[0.03]">
                {insp.media_type === 'video' || insp.media_type === 'reel' ? (
                  <VideoCamera size={40} className="text-dim" />
                ) : (
                  <Image size={40} className="text-dim" />
                )}
              </div>
              <div className="flex flex-1 flex-col gap-2 p-4">
                <div className="flex items-center justify-between">
                  <span className="inline-flex h-6 items-center rounded-lg bg-white/5 px-2 text-[11px] font-semibold uppercase text-muted">
                    {MEDIA_TYPE_LABELS[insp.media_type]}
                  </span>
                  <span className="inline-flex h-6 items-center rounded-lg bg-white/5 px-2 text-[11px] font-semibold text-muted">
                    {INSPIRATION_STATUS_LABELS[insp.status]}
                  </span>
                </div>
                {insp.caption && (
                  <p className="line-clamp-2 text-xs text-muted">{insp.caption}</p>
                )}
                <div className="mt-auto flex items-center justify-between pt-2">
                  <span className="text-xs text-dim">
                    {insp.engagement.toLocaleString('fr-FR')} engagements
                  </span>
                  <div className="flex gap-1">
                    <button
                      type="button"
                      className="icon-btn"
                      title="Ajouter aux favoris"
                      onClick={() => handleAction(insp, 'favorite')}
                    >
                      <Star size={16} />
                    </button>
                    <button
                      type="button"
                      className="icon-btn"
                      title="Creer un snipe"
                      onClick={() => handleAction(insp, 'snipe')}
                    >
                      <Target size={16} />
                    </button>
                    <button
                      type="button"
                      className="icon-btn"
                      title="Ecarter"
                      onClick={() => handleAction(insp, 'dismiss')}
                    >
                      <XCircle size={16} />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// --- Snipes tab ------------------------------------------------------------

function SnipesTab() {
  const [statusFilter, setStatusFilter] = useState<SnipeStatus | ''>('')
  const [priorityFilter, setPriorityFilter] = useState<SnipePriority | ''>('')
  const snipes = useSnipes({
    status: statusFilter || undefined,
    priority: priorityFilter || undefined,
  })
  const update = useSaveSnipe()
  const personas = usePersonas()

  const personaLabels = useMemo(
    () => new Map(personas.data?.map((p) => [p.id, `${p.first_name} ${p.last_name ?? ''}`.trim()]) ?? []),
    [personas.data],
  )

  return (
    <div>
      <div className="mb-4 flex items-center gap-3">
        <select
          className="field w-44"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as SnipeStatus | '')}
        >
          <option value="">Tous les statuts</option>
          {SNIPE_STATUSES.map((s) => (
            <option key={s} value={s}>
              {SNIPE_STATUS_LABELS[s]}
            </option>
          ))}
        </select>
        <select
          className="field w-36"
          value={priorityFilter}
          onChange={(e) => setPriorityFilter(e.target.value as SnipePriority | '')}
        >
          <option value="">Toutes priorites</option>
          {SNIPE_PRIORITIES.map((p) => (
            <option key={p} value={p}>
              {PRIORITY_LABELS[p]}
            </option>
          ))}
        </select>
        <span className="text-xs text-muted">
          {snipes.data ? `${snipes.data.length} snipe${snipes.data.length > 1 ? 's' : ''}` : ''}
        </span>
      </div>

      {snipes.isLoading && <Loading />}
      {snipes.isError && <ErrorState error={snipes.error} onRetry={() => snipes.refetch()} />}
      {snipes.data?.length === 0 && (
        <Empty>
          {statusFilter || priorityFilter
            ? 'Aucun snipe ne correspond aux filtres.'
            : 'Aucun snipe pour le moment.'}
        </Empty>
      )}

      {snipes.data && snipes.data.length > 0 && (
        <div className="card overflow-hidden">
          <table className="w-full text-left text-[13px]">
            <thead>
              <tr className="border-b border-line text-[11px] uppercase tracking-wider text-muted">
                <th className="px-5 py-3 font-semibold">Inspiration</th>
                <th className="px-5 py-3 font-semibold">Persona cible</th>
                <th className="px-5 py-3 font-semibold">Priorite</th>
                <th className="px-5 py-3 font-semibold">Statut</th>
                <th className="px-5 py-3 font-semibold">Echeance</th>
                <th className="px-5 py-3 font-semibold">Cree le</th>
              </tr>
            </thead>
            <tbody>
              {snipes.data.map((sn) => (
                <tr
                  key={sn.id}
                  className="border-b border-line last:border-0 hover:bg-white/[0.02]"
                >
                  <td className="px-5 py-3 font-mono text-xs text-muted">
                    {sn.inspiration_id.slice(0, 8)}...
                  </td>
                  <td className="px-5 py-3 text-muted">
                    {sn.target_persona_id
                      ? personaLabels.get(sn.target_persona_id) ?? sn.target_persona_id.slice(0, 8)
                      : '—'}
                  </td>
                  <td className="px-5 py-3">
                    <span
                      className="inline-flex h-6 items-center rounded-lg px-2 text-[11px] font-semibold"
                      style={{
                        background: `${PRIORITY_COLORS[sn.priority]}20`,
                        color: PRIORITY_COLORS[sn.priority],
                      }}
                    >
                      {PRIORITY_LABELS[sn.priority]}
                    </span>
                  </td>
                  <td className="px-5 py-3">
                    <select
                      className="field w-36 text-xs"
                      value={sn.status}
                      onChange={(e) =>
                        update.mutate({ id: sn.id, data: { ...sn, status: e.target.value as SnipeStatus } })
                      }
                      disabled={update.isPending}
                    >
                      {SNIPE_STATUSES.map((s) => (
                        <option key={s} value={s}>
                          {SNIPE_STATUS_LABELS[s]}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-5 py-3 text-muted">
                    {sn.due_date
                      ? new Date(sn.due_date).toLocaleDateString('fr-FR')
                      : '—'}
                  </td>
                  <td className="px-5 py-3 text-muted">
                    {new Date(sn.created_at).toLocaleDateString('fr-FR')}
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

// --- Album form modal ------------------------------------------------------

function AlbumForm({ album, onClose }: { album?: Album; onClose: () => void }) {
  const save = useSaveAlbum()
  const personas = usePersonas()

  const [form, setForm] = useState<AlbumInput>({
    name: album?.name ?? '',
    description: album?.description ?? null,
    persona_id: album?.persona_id ?? null,
  })

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    save.mutate({ id: album?.id, data: form }, { onSuccess: onClose })
  }

  return (
    <Modal
      title={album ? `Modifier « ${album.name} »` : 'Nouvel album'}
      onClose={onClose}
      width={480}
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Annuler
          </button>
          <button
            type="submit"
            form="album-form"
            className="btn btn-primary"
            disabled={save.isPending || !form.name.trim()}
          >
            <FloppyDisk size={16} /> Enregistrer
          </button>
        </>
      }
    >
      <form id="album-form" onSubmit={submit} className="space-y-4">
        <div>
          <label className="label">Nom</label>
          <input
            className="field"
            placeholder="Mon album"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            autoFocus
          />
        </div>
        <div>
          <label className="label">Description</label>
          <textarea
            className="field"
            rows={3}
            placeholder="Description (optionnel)"
            value={form.description ?? ''}
            onChange={(e) => setForm({ ...form, description: e.target.value || null })}
          />
        </div>
        <div>
          <label className="label">Persona</label>
          <select
            className="field"
            value={form.persona_id ?? ''}
            onChange={(e) =>
              setForm({ ...form, persona_id: e.target.value || null })
            }
          >
            <option value="">Aucune</option>
            {personas.data?.map((p) => (
              <option key={p.id} value={p.id}>
                {`${p.first_name} ${p.last_name ?? ''}`.trim()}
              </option>
            ))}
          </select>
        </div>
      </form>
    </Modal>
  )
}

// --- Albums tab ------------------------------------------------------------

function AlbumsTab() {
  const albums = useAlbums()
  const favorites = useFavorites()
  const personas = usePersonas()
  const del = useDeleteAlbum()

  const [editing, setEditing] = useState<Album | null | undefined>(undefined)
  const [deleting, setDeleting] = useState<Album | null>(null)

  const personaLabels = useMemo(
    () => new Map(personas.data?.map((p) => [p.id, `${p.first_name} ${p.last_name ?? ''}`.trim()]) ?? []),
    [personas.data],
  )

  const favCountByAlbum = useMemo(() => {
    const map = new Map<string, number>()
    for (const f of favorites.data ?? []) {
      if (f.album_id) {
        map.set(f.album_id, (map.get(f.album_id) ?? 0) + 1)
      }
    }
    return map
  }, [favorites.data])

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <span className="text-xs text-muted">
          {albums.data ? `${albums.data.length} album${albums.data.length > 1 ? 's' : ''}` : ''}
        </span>
        <button type="button" className="btn btn-primary" onClick={() => setEditing(null)}>
          <Plus size={16} weight="bold" /> Nouvel album
        </button>
      </div>

      {albums.isLoading && <Loading />}
      {albums.isError && <ErrorState error={albums.error} onRetry={() => albums.refetch()} />}
      {albums.data?.length === 0 && (
        <Empty>Aucun album pour le moment.</Empty>
      )}

      {albums.data && albums.data.length > 0 && (
        <div className="grid grid-cols-3 gap-4">
          {albums.data.map((a) => (
            <div key={a.id} className="card flex flex-col gap-3 p-5">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2">
                  <FolderSimple size={20} className="text-accent-1" />
                  <h3 className="font-semibold">{a.name}</h3>
                </div>
                <div className="flex gap-1">
                  <button
                    type="button"
                    className="icon-btn"
                    aria-label={`Modifier ${a.name}`}
                    onClick={() => setEditing(a)}
                  >
                    <PencilSimple size={16} />
                  </button>
                  <button
                    type="button"
                    className="icon-btn"
                    aria-label={`Supprimer ${a.name}`}
                    onClick={() => setDeleting(a)}
                  >
                    <Trash size={16} />
                  </button>
                </div>
              </div>
              {a.description && (
                <p className="line-clamp-2 text-xs text-muted">{a.description}</p>
              )}
              <div className="mt-auto flex items-center justify-between text-xs text-muted">
                <span>{favCountByAlbum.get(a.id) ?? 0} element(s)</span>
                {a.persona_id && (
                  <span className="inline-flex h-6 items-center rounded-lg bg-white/5 px-2 text-[11px] font-semibold">
                    {personaLabels.get(a.persona_id) ?? 'Persona'}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {editing !== undefined && (
        <AlbumForm album={editing ?? undefined} onClose={() => setEditing(undefined)} />
      )}

      {deleting && (
        <ConfirmDialog
          title="Supprimer l'album"
          message={`L'album « ${deleting.name} » sera supprime definitivement.`}
          pending={del.isPending}
          onCancel={() => setDeleting(null)}
          onConfirm={() => del.mutate(deleting.id, { onSuccess: () => setDeleting(null) })}
        />
      )}
    </div>
  )
}

// --- Main page -------------------------------------------------------------

const TABS: { key: Tab; label: string }[] = [
  { key: 'sources', label: 'Sources' },
  { key: 'inspirations', label: 'Inspirations' },
  { key: 'snipes', label: 'Snipes' },
  { key: 'albums', label: 'Albums' },
]

export default function VeillePage() {
  const [tab, setTab] = useState<Tab>('sources')

  return (
    <div>
      <KpiBar />

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

      {tab === 'sources' && <SourcesTab />}
      {tab === 'inspirations' && <InspirationsTab />}
      {tab === 'snipes' && <SnipesTab />}
      {tab === 'albums' && <AlbumsTab />}
    </div>
  )
}
