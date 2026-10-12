import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { PencilSimple, Plus, Trash, UploadSimple } from '@phosphor-icons/react'
import ConfirmDialog from '../../components/ConfirmDialog'
import PlatformBadge, { PLATFORM_META } from '../../components/PlatformBadge'
import { Empty, ErrorState, Loading } from '../../components/StateBlock'
import { useDeleteTarget, useMarches, useNiches, useTargets } from '../../hooks/useApi'
import { PLATFORMS, type Platform } from '../../types/compte'
import { TARGET_STATUSES, type Target, type TargetStatus } from '../../types/target'
import BulkImportModal from './BulkImportModal'
import TargetForm from './TargetForm'

const STATUS_COLORS: Record<TargetStatus, string> = {
  ok: '#22c55e',
  prive: '#f59e0b',
  renomme: '#4b7bf5',
  banni: '#ef4444',
}

const STATUS_LABELS: Record<TargetStatus, string> = {
  ok: 'OK',
  prive: 'Prive',
  renomme: 'Renomme',
  banni: 'Banni',
}

const isPlatform = (v: string | null): v is Platform => PLATFORMS.includes(v as Platform)
const isStatus = (v: string | null): v is TargetStatus => TARGET_STATUSES.includes(v as TargetStatus)

export default function TargetsPage() {
  const [params, setParams] = useSearchParams()
  const plat = params.get('plat')
  const market = params.get('market') ?? undefined
  const statusParam = params.get('status')
  const plateforme = isPlatform(plat) ? plat : undefined
  const status = isStatus(statusParam) ? statusParam : undefined

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }

  const targets = useTargets({ plateforme, market, status })
  const marches = useMarches()
  const niches = useNiches()
  const del = useDeleteTarget()

  const [editing, setEditing] = useState<Target | null | undefined>(undefined)
  const [deleting, setDeleting] = useState<Target | null>(null)
  const [showBulk, setShowBulk] = useState(false)

  const nicheLabels = useMemo(
    () => new Map(niches.data?.map((n) => [n.id, n.label]) ?? []),
    [niches.data],
  )

  const filtered = Boolean(plateforme || market || status)

  return (
    <>
      <div className="mb-6 flex items-center gap-3">
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
        <select
          className="field w-40"
          aria-label="Filtrer par marche"
          value={market ?? ''}
          onChange={(e) => setFilter('market', e.target.value)}
        >
          <option value="">Tous les marches</option>
          {marches.data?.map((m) => (
            <option key={m.code} value={m.code}>
              {m.label}
            </option>
          ))}
        </select>
        <select
          className="field w-36"
          aria-label="Filtrer par statut"
          value={status ?? ''}
          onChange={(e) => setFilter('status', e.target.value)}
        >
          <option value="">Tous les statuts</option>
          {TARGET_STATUSES.map((s) => (
            <option key={s} value={s}>
              {STATUS_LABELS[s]}
            </option>
          ))}
        </select>
        <span className="text-[13px] text-muted">
          {targets.data ? `${targets.data.length} target${targets.data.length > 1 ? 's' : ''}` : ''}
        </span>
        <div className="ml-auto flex gap-2">
          <button type="button" className="btn btn-ghost" onClick={() => setShowBulk(true)}>
            <UploadSimple size={16} /> Import
          </button>
          <button type="button" className="btn btn-primary" onClick={() => setEditing(null)}>
            <Plus size={16} weight="bold" /> Nouvelle target
          </button>
        </div>
      </div>

      {targets.isLoading && <Loading />}
      {targets.isError && <ErrorState error={targets.error} onRetry={() => targets.refetch()} />}
      {targets.data?.length === 0 && (
        <Empty>
          {filtered
            ? 'Aucune target ne correspond aux filtres.'
            : 'Aucune target pour le moment.'}
        </Empty>
      )}

      {targets.data && targets.data.length > 0 && (
        <div className="card overflow-hidden">
          <table className="w-full text-left text-[13px]">
            <thead>
              <tr className="border-b border-line text-[11px] uppercase tracking-wider text-muted">
                <th className="px-5 py-3 font-semibold">Handle</th>
                <th className="px-5 py-3 font-semibold">Plateforme</th>
                <th className="px-5 py-3 font-semibold">Marche</th>
                <th className="px-5 py-3 font-semibold">Niche</th>
                <th className="px-5 py-3 font-semibold">Statut</th>
                <th className="px-5 py-3 font-semibold">Source</th>
                <th className="w-24 px-5 py-3" />
              </tr>
            </thead>
            <tbody>
              {targets.data.map((t) => (
                <tr
                  key={t.id}
                  className="border-b border-line last:border-0 hover:bg-white/[0.02]"
                >
                  <td className="px-5 py-3 font-semibold">@{t.handle}</td>
                  <td className="px-5 py-3">
                    <PlatformBadge platform={t.plateforme} withLabel />
                  </td>
                  <td className="px-5 py-3 text-muted">{t.market ?? '—'}</td>
                  <td className="px-5 py-3 text-muted">
                    {t.niche_id ? nicheLabels.get(t.niche_id) ?? `#${t.niche_id}` : '—'}
                  </td>
                  <td className="px-5 py-3">
                    <span className="inline-flex items-center gap-2">
                      <span
                        className="h-2 w-2 rounded-full"
                        style={{ background: STATUS_COLORS[t.status] }}
                      />
                      {STATUS_LABELS[t.status] ?? t.status}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-muted capitalize">{t.source}</td>
                  <td className="px-5 py-3">
                    <div className="flex justify-end gap-1">
                      <button
                        type="button"
                        className="icon-btn"
                        aria-label={`Modifier @${t.handle}`}
                        onClick={() => setEditing(t)}
                      >
                        <PencilSimple size={16} />
                      </button>
                      <button
                        type="button"
                        className="icon-btn"
                        aria-label={`Supprimer @${t.handle}`}
                        onClick={() => setDeleting(t)}
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
        <TargetForm target={editing ?? undefined} onClose={() => setEditing(undefined)} />
      )}

      {deleting && (
        <ConfirmDialog
          title="Supprimer la target"
          message={`La target @${deleting.handle} sera supprimee definitivement.`}
          pending={del.isPending}
          onCancel={() => setDeleting(null)}
          onConfirm={() => del.mutate(deleting.id, { onSuccess: () => setDeleting(null) })}
        />
      )}

      {showBulk && <BulkImportModal onClose={() => setShowBulk(false)} />}
    </>
  )
}
