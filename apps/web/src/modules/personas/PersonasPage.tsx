import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { MagnifyingGlass, PencilSimple, Plus, Trash } from '@phosphor-icons/react'
import ConfirmDialog from '../../components/ConfirmDialog'
import PlatformBadge from '../../components/PlatformBadge'
import { Empty, ErrorState, Loading } from '../../components/StateBlock'
import { useDeletePersona, useNiches, usePersonas } from '../../hooks/useApi'
import type { Persona } from '../../types/persona'
import PersonaForm from './PersonaForm'

function Avatar({ persona }: { persona: Persona }) {
  const initials = `${persona.first_name[0] ?? ''}${persona.last_name?.[0] ?? ''}`.toUpperCase()
  if (persona.photo_url) {
    return <img src={persona.photo_url} alt="" className="h-12 w-12 shrink-0 rounded-full object-cover" />
  }
  return (
    <div
      className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full text-sm font-bold"
      style={{ background: persona.color ?? 'var(--accent-1)' }}
    >
      {initials}
    </div>
  )
}

export default function PersonasPage() {
  const personas = usePersonas()
  const niches = useNiches()
  const del = useDeletePersona()

  const [search, setSearch] = useState('')
  // undefined = ferme, null = creation, Persona = edition
  const [editing, setEditing] = useState<Persona | null | undefined>(undefined)
  const [deleting, setDeleting] = useState<Persona | null>(null)

  const nicheLabels = useMemo(
    () => new Map(niches.data?.map((n) => [n.id, n.label]) ?? []),
    [niches.data],
  )

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return personas.data ?? []
    return (personas.data ?? []).filter((p) =>
      [p.first_name, p.last_name, p.city, p.market].some((v) => v?.toLowerCase().includes(q)),
    )
  }, [personas.data, search])

  return (
    <>
      <div className="mb-6 flex items-center gap-3">
        <div className="relative w-72">
          <MagnifyingGlass size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-dim" />
          <input
            className="field pl-9"
            placeholder="Rechercher une persona"
            aria-label="Rechercher une persona"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <span className="text-[13px] text-muted">
          {personas.data ? `${filtered.length} persona${filtered.length > 1 ? 's' : ''}` : ''}
        </span>
        <button type="button" className="btn btn-primary ml-auto" onClick={() => setEditing(null)}>
          <Plus size={16} weight="bold" /> Nouvelle persona
        </button>
      </div>

      {personas.isLoading && <Loading />}
      {personas.isError && <ErrorState error={personas.error} onRetry={() => personas.refetch()} />}
      {personas.data && filtered.length === 0 && (
        <Empty
          action={
            !search && (
              <button type="button" className="btn btn-ghost" onClick={() => setEditing(null)}>
                Creer la premiere persona
              </button>
            )
          }
        >
          {search ? 'Aucune persona ne correspond a la recherche.' : 'Aucune persona pour le moment.'}
        </Empty>
      )}

      <div className="grid grid-cols-3 gap-5 min-[1680px]:grid-cols-4">
        {filtered.map((p) => (
          <article key={p.id} className="card flex flex-col gap-4 p-5">
            <div className="flex items-start gap-3">
              <Avatar persona={p} />
              <div className="min-w-0 flex-1">
                <div className="truncate text-base font-bold">
                  {p.first_name} {p.last_name}
                </div>
                <div className="truncate text-[13px] text-muted">
                  {[p.market, p.city, p.age != null ? `${p.age} ans` : null].filter(Boolean).join(' · ') || 'Profil a completer'}
                </div>
              </div>
              <button type="button" className="icon-btn" aria-label={`Modifier ${p.first_name}`} onClick={() => setEditing(p)}>
                <PencilSimple size={16} />
              </button>
              <button type="button" className="icon-btn" aria-label={`Supprimer ${p.first_name}`} onClick={() => setDeleting(p)}>
                <Trash size={16} />
              </button>
            </div>

            <div className="flex flex-wrap gap-1.5">
              {p.platforms?.map((pl) => <PlatformBadge key={pl} platform={pl} withLabel />)}
              {p.niches?.map((id) => (
                <span key={id} className="inline-flex h-6 items-center rounded-lg bg-accent-1/15 px-2 text-xs font-medium text-white/80">
                  {nicheLabels.get(id) ?? `#${id}`}
                </span>
              ))}
            </div>

            <div className="mt-auto flex items-center justify-between border-t border-line pt-3 text-[13px]">
              <span className="text-muted">
                {p.comptes.length} compte{p.comptes.length > 1 ? 's' : ''}
              </span>
              <Link to={`/comptes?persona=${p.id}`} className="font-semibold text-accent-2 hover:underline">
                Voir les comptes
              </Link>
            </div>
          </article>
        ))}
      </div>

      {editing !== undefined && <PersonaForm persona={editing ?? undefined} onClose={() => setEditing(undefined)} />}

      {deleting && (
        <ConfirmDialog
          title="Supprimer la persona"
          message={`${deleting.first_name} sera supprimee. Ses ${deleting.comptes.length} compte(s) seront conserves, sans persona.`}
          pending={del.isPending}
          onCancel={() => setDeleting(null)}
          onConfirm={() => del.mutate(deleting.id, { onSuccess: () => setDeleting(null) })}
        />
      )}
    </>
  )
}
