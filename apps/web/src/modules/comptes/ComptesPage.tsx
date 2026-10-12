import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { PencilSimple, Plus, Trash } from '@phosphor-icons/react'
import ConfirmDialog from '../../components/ConfirmDialog'
import PlatformBadge, { PLATFORM_META } from '../../components/PlatformBadge'
import { Empty, ErrorState, Loading } from '../../components/StateBlock'
import { useComptes, useDeleteCompte, usePersonas } from '../../hooks/useApi'
import { PLATFORMS, type Compte, type Platform } from '../../types/compte'
import CompteForm from './CompteForm'
import { STATUS_COLORS, STATUS_LABELS } from './labels'

const isPlatform = (v: string | null): v is Platform => PLATFORMS.includes(v as Platform)

export default function ComptesPage() {
  // Filtres dans l'URL : /comptes?persona=<id>&plat=ig (partageable, lien depuis Personas)
  const [params, setParams] = useSearchParams()
  const personaId = params.get('persona') ?? ''
  const plat = params.get('plat')
  const plateforme = isPlatform(plat) ? plat : undefined

  const setFilter = (key: 'persona' | 'plat', value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }

  const comptes = useComptes({ persona_id: personaId || undefined, plateforme })
  const personas = usePersonas()
  const del = useDeleteCompte()

  const [editing, setEditing] = useState<Compte | null | undefined>(undefined)
  const [deleting, setDeleting] = useState<Compte | null>(null)

  const personaById = useMemo(
    () => new Map(personas.data?.map((p) => [p.id, p]) ?? []),
    [personas.data],
  )
  const filtered = Boolean(personaId || plateforme)

  return (
    <>
      <div className="mb-6 flex items-center gap-3">
        <select className="field w-56" aria-label="Filtrer par persona" value={personaId}
          onChange={(e) => setFilter('persona', e.target.value)}>
          <option value="">Toutes les personas</option>
          {personas.data?.map((p) => (
            <option key={p.id} value={p.id}>{p.first_name} {p.last_name ?? ''}</option>
          ))}
        </select>
        <select className="field w-48" aria-label="Filtrer par plateforme" value={plateforme ?? ''}
          onChange={(e) => setFilter('plat', e.target.value)}>
          <option value="">Toutes les plateformes</option>
          {PLATFORMS.map((p) => <option key={p} value={p}>{PLATFORM_META[p].label}</option>)}
        </select>
        <span className="text-[13px] text-muted">
          {comptes.data ? `${comptes.data.length} compte${comptes.data.length > 1 ? 's' : ''}` : ''}
        </span>
        <button type="button" className="btn btn-primary ml-auto" onClick={() => setEditing(null)}>
          <Plus size={16} weight="bold" /> Nouveau compte
        </button>
      </div>

      {comptes.isLoading && <Loading />}
      {comptes.isError && <ErrorState error={comptes.error} onRetry={() => comptes.refetch()} />}
      {comptes.data?.length === 0 && (
        <Empty>{filtered ? 'Aucun compte ne correspond aux filtres.' : 'Aucun compte pour le moment.'}</Empty>
      )}

      {comptes.data && comptes.data.length > 0 && (
        <div className="card overflow-hidden">
          <table className="w-full text-left text-[13px]">
            <thead>
              <tr className="border-b border-line text-[11px] uppercase tracking-wider text-muted">
                <th className="px-5 py-3 font-semibold">Compte</th>
                <th className="px-5 py-3 font-semibold">Plateforme</th>
                <th className="px-5 py-3 font-semibold">Persona</th>
                <th className="px-5 py-3 font-semibold">Workflow</th>
                <th className="px-5 py-3 font-semibold">Statut</th>
                <th className="px-5 py-3 text-right font-semibold">Sessions</th>
                <th className="px-5 py-3 text-right font-semibold">Follows</th>
                <th className="w-24 px-5 py-3" />
              </tr>
            </thead>
            <tbody>
              {comptes.data.map((c) => {
                const persona = c.persona_id ? personaById.get(c.persona_id) : undefined
                return (
                  <tr key={c.id} className="border-b border-line last:border-0 hover:bg-white/[0.02]">
                    <td className="px-5 py-3 font-semibold">@{c.handle}</td>
                    <td className="px-5 py-3"><PlatformBadge platform={c.plateforme} withLabel /></td>
                    <td className="px-5 py-3">
                      {persona ? (
                        <span className="inline-flex items-center gap-2">
                          <span className="h-2.5 w-2.5 rounded-full" style={{ background: persona.color ?? 'var(--accent-1)' }} />
                          {persona.first_name} {persona.last_name}
                        </span>
                      ) : (
                        <span className="text-dim">Aucune</span>
                      )}
                    </td>
                    <td className="px-5 py-3 text-muted">{c.workflow}</td>
                    <td className="px-5 py-3">
                      <span className="inline-flex items-center gap-2">
                        <span className="h-2 w-2 rounded-full" style={{ background: STATUS_COLORS[c.status] }} />
                        {STATUS_LABELS[c.status] ?? c.status}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-right tabular-nums text-muted">{c.sessions}</td>
                    <td className="px-5 py-3 text-right tabular-nums text-muted">{c.follows}</td>
                    <td className="px-5 py-3">
                      <div className="flex justify-end gap-1">
                        <button type="button" className="icon-btn" aria-label={`Modifier @${c.handle}`} onClick={() => setEditing(c)}>
                          <PencilSimple size={16} />
                        </button>
                        <button type="button" className="icon-btn" aria-label={`Supprimer @${c.handle}`} onClick={() => setDeleting(c)}>
                          <Trash size={16} />
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {editing !== undefined && (
        <CompteForm
          compte={editing ?? undefined}
          personas={personas.data ?? []}
          defaultPersonaId={personaId || undefined}
          onClose={() => setEditing(undefined)}
        />
      )}

      {deleting && (
        <ConfirmDialog
          title="Supprimer le compte"
          message={`Le compte @${deleting.handle} sera supprime definitivement.`}
          pending={del.isPending}
          onCancel={() => setDeleting(null)}
          onConfirm={() => del.mutate(deleting.id, { onSuccess: () => setDeleting(null) })}
        />
      )}
    </>
  )
}
