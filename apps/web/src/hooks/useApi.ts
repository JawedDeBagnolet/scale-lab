import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'
import { toast } from '../stores/toast'
import type { Compte, CompteFilters, CompteInput } from '../types/compte'
import type { Persona, PersonaInput } from '../types/persona'
import type { Marche, Niche } from '../types/referentiel'

// --- Wrappers generiques -----------------------------------------------------

export function useApiQuery<T>(key: readonly unknown[], path: string, staleTime?: number) {
  return useQuery({ queryKey: key, queryFn: () => api<T>(path), staleTime })
}

/** Mutation qui invalide des query keys et affiche un toast (succes / erreur). */
export function useApiMutation<TIn, TOut>(
  fn: (input: TIn) => Promise<TOut>,
  opts: { invalidate: readonly (readonly unknown[])[]; success: string },
) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      opts.invalidate.forEach((queryKey) => qc.invalidateQueries({ queryKey }))
      toast.success(opts.success)
    },
    onError: (err: Error) => toast.error(err.message),
  })
}

const body = (data: unknown) => JSON.stringify(data)
// Une persona embarque ses comptes : toute ecriture invalide les deux listes
const BOTH = [['personas'], ['comptes']] as const

// --- Referentiels (donnees lentes) -------------------------------------------

const FIVE_MIN = 5 * 60_000
export const useNiches = () => useApiQuery<Niche[]>(['niches'], '/api/niches', FIVE_MIN)
export const useMarches = () => useApiQuery<Marche[]>(['marches'], '/api/marches', FIVE_MIN)

// --- Personas ----------------------------------------------------------------

export const usePersonas = () => useApiQuery<Persona[]>(['personas'], '/api/personas')

export const useSavePersona = () =>
  useApiMutation(
    ({ id, data }: { id?: string; data: PersonaInput }) =>
      id
        ? api<Persona>(`/api/personas/${id}`, { method: 'PATCH', body: body(data) })
        : api<Persona>('/api/personas', { method: 'POST', body: body(data) }),
    { invalidate: BOTH, success: 'Persona enregistree' },
  )

export const useDeletePersona = () =>
  useApiMutation((id: string) => api<void>(`/api/personas/${id}`, { method: 'DELETE' }), {
    invalidate: BOTH,
    success: 'Persona supprimee',
  })

// --- Comptes -----------------------------------------------------------------

export function useComptes(filters: CompteFilters = {}) {
  const params = new URLSearchParams()
  if (filters.persona_id) params.set('persona_id', filters.persona_id)
  if (filters.plateforme) params.set('plateforme', filters.plateforme)
  const qs = params.toString()
  return useApiQuery<Compte[]>(['comptes', filters], `/api/comptes${qs ? `?${qs}` : ''}`)
}

export const useSaveCompte = () =>
  useApiMutation(
    ({ id, data }: { id?: string; data: Partial<CompteInput> }) =>
      id
        ? api<Compte>(`/api/comptes/${id}`, { method: 'PATCH', body: body(data) })
        : api<Compte>('/api/comptes', { method: 'POST', body: body(data) }),
    { invalidate: BOTH, success: 'Compte enregistre' },
  )

export const useDeleteCompte = () =>
  useApiMutation((id: string) => api<void>(`/api/comptes/${id}`, { method: 'DELETE' }), {
    invalidate: BOTH,
    success: 'Compte supprime',
  })
