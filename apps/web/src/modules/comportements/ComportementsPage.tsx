import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { PencilSimple, Plus, SlidersHorizontal, Star, Trash } from '@phosphor-icons/react'
import ConfirmDialog from '../../components/ConfirmDialog'
import PlatformBadge, { PLATFORM_META } from '../../components/PlatformBadge'
import { Empty, ErrorState, Loading } from '../../components/StateBlock'
import { useDeletePreset, usePresets } from '../../hooks/useApi'
import { PLATFORMS, type Platform } from '../../types/compte'
import { SESSION_TYPES, SESSION_TYPE_LABELS, type Preset, type SessionType } from '../../types/preset'
import PresetForm from './PresetForm'

const isPlatform = (v: string | null): v is Platform => PLATFORMS.includes(v as Platform)
const isSessionType = (v: string | null): v is SessionType =>
  SESSION_TYPES.includes(v as SessionType)

export default function ComportementsPage() {
  const [params, setParams] = useSearchParams()
  const plat = params.get('plat')
  const st = params.get('type')
  const plateforme = isPlatform(plat) ? plat : undefined
  const session_type = isSessionType(st) ? st : undefined

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }

  const presets = usePresets({ plateforme, session_type })
  const del = useDeletePreset()

  const [editing, setEditing] = useState<Preset | null | undefined>(undefined)
  const [deleting, setDeleting] = useState<Preset | null>(null)

  const filtered = Boolean(plateforme || session_type)

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
          className="field w-44"
          aria-label="Filtrer par type"
          value={session_type ?? ''}
          onChange={(e) => setFilter('type', e.target.value)}
        >
          <option value="">Tous les types</option>
          {SESSION_TYPES.map((t) => (
            <option key={t} value={t}>
              {SESSION_TYPE_LABELS[t]}
            </option>
          ))}
        </select>
        <span className="text-[13px] text-muted">
          {presets.data
            ? `${presets.data.length} preset${presets.data.length > 1 ? 's' : ''}`
            : ''}
        </span>
        <button
          type="button"
          className="btn btn-primary ml-auto"
          onClick={() => setEditing(null)}
        >
          <Plus size={16} weight="bold" /> Nouveau preset
        </button>
      </div>

      {presets.isLoading && <Loading />}
      {presets.isError && (
        <ErrorState error={presets.error} onRetry={() => presets.refetch()} />
      )}
      {presets.data?.length === 0 && (
        <Empty>
          {filtered
            ? 'Aucun preset ne correspond aux filtres.'
            : 'Aucun preset pour le moment.'}
        </Empty>
      )}

      <div className="grid grid-cols-3 gap-5 min-[1680px]:grid-cols-4">
        {presets.data?.map((p) => {
          const probs = (p.config.probabilities ?? {}) as Record<string, number>
          const pauses = (p.config.pauses ?? { min: 0, max: 0 }) as {
            min: number
            max: number
          }
          const durations = (p.config.durations ?? { min: 0, max: 0 }) as {
            min: number
            max: number
          }

          return (
            <article key={p.id} className="card flex flex-col gap-4 p-5">
              <div className="flex items-start gap-3">
                <div
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl"
                  style={{ background: 'rgba(109, 94, 240, 0.15)' }}
                >
                  <SlidersHorizontal size={20} className="text-accent-1" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 truncate text-base font-bold">
                    {p.name}
                    {p.is_default && (
                      <Star size={14} weight="fill" className="text-warning" />
                    )}
                  </div>
                  <div className="truncate text-xs text-muted">
                    {SESSION_TYPE_LABELS[p.session_type as SessionType] ?? p.session_type}
                    {p.description && ` — ${p.description}`}
                  </div>
                </div>
                <button
                  type="button"
                  className="icon-btn"
                  aria-label={`Modifier ${p.name}`}
                  onClick={() => setEditing(p)}
                >
                  <PencilSimple size={16} />
                </button>
                <button
                  type="button"
                  className="icon-btn"
                  aria-label={`Supprimer ${p.name}`}
                  onClick={() => setDeleting(p)}
                >
                  <Trash size={16} />
                </button>
              </div>

              <div className="flex gap-1.5">
                <PlatformBadge platform={p.plateforme as Platform} withLabel />
              </div>

              {/* Config preview */}
              <div className="space-y-2 rounded-xl bg-white/[0.02] p-3 text-xs">
                {Object.entries(probs).length > 0 && (
                  <div>
                    <div className="mb-1 font-semibold text-muted">Probabilites</div>
                    <div className="flex flex-wrap gap-x-3 gap-y-1">
                      {Object.entries(probs).map(([k, v]) => (
                        <span key={k} className="text-muted">
                          <span className="capitalize">{k.replace(/_/g, ' ')}</span>{' '}
                          <span className="font-mono text-white">{Math.round(v * 100)}%</span>
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                <div className="flex gap-6 text-muted">
                  <span>
                    Pauses:{' '}
                    <span className="font-mono text-white">
                      {pauses.min}–{pauses.max}s
                    </span>
                  </span>
                  <span>
                    Durees:{' '}
                    <span className="font-mono text-white">
                      {durations.min}–{durations.max}min
                    </span>
                  </span>
                </div>
              </div>
            </article>
          )
        })}
      </div>

      {editing !== undefined && (
        <PresetForm preset={editing ?? undefined} onClose={() => setEditing(undefined)} />
      )}

      {deleting && (
        <ConfirmDialog
          title="Supprimer le preset"
          message={`Le preset « ${deleting.name} » sera supprime definitivement.`}
          pending={del.isPending}
          onCancel={() => setDeleting(null)}
          onConfirm={() => del.mutate(deleting.id, { onSuccess: () => setDeleting(null) })}
        />
      )}
    </>
  )
}
