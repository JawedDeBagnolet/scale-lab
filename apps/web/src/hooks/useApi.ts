import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'
import { toast } from '../stores/toast'
import type { Compte, CompteFilters, CompteInput } from '../types/compte'
import type { DashboardStats } from '../types/dashboard'
import type { AlertRule, AlertRuleCreate, EventFilters, Incident, LogEvent, LogStats } from '../types/log'
import type { Persona, PersonaInput } from '../types/persona'
import type { Preset, PresetFilters, PresetInput } from '../types/preset'
import type { Marche, Niche } from '../types/referentiel'
import type { IntegrationUpdate, NotificationsConfig, WorkspaceSettings, WorkspaceUpdate } from '../types/settings'
import type { Target, TargetFilters, TargetInput } from '../types/target'

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

// --- Dashboard ---------------------------------------------------------------

export const useDashboardStats = () =>
  useApiQuery<DashboardStats>(['dashboardStats'], '/api/dashboard/stats')

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

// --- Settings ----------------------------------------------------------------

export const useSettings = () =>
  useApiQuery<WorkspaceSettings>(['settings'], '/api/settings', FIVE_MIN)

export const useUpdateWorkspace = () =>
  useApiMutation(
    (data: WorkspaceUpdate) =>
      api<WorkspaceSettings>('/api/settings/workspace', { method: 'PATCH', body: body(data) }),
    { invalidate: [['settings']], success: 'Parametres sauvegardes' },
  )

export const useUpdateIntegration = () =>
  useApiMutation(
    ({ provider, data }: { provider: string; data: IntegrationUpdate }) =>
      api<WorkspaceSettings>(`/api/settings/integrations/${provider}`, {
        method: 'PATCH',
        body: body(data),
      }),
    { invalidate: [['settings']], success: 'Integration mise a jour' },
  )

export const useUpdateNotifications = () =>
  useApiMutation(
    (data: NotificationsConfig) =>
      api<WorkspaceSettings>('/api/settings/notifications', { method: 'PATCH', body: body(data) }),
    { invalidate: [['settings']], success: 'Notifications mises a jour' },
  )

// --- Targets -----------------------------------------------------------------

export function useTargets(filters: TargetFilters = {}) {
  const params = new URLSearchParams()
  if (filters.plateforme) params.set('plateforme', filters.plateforme)
  if (filters.market) params.set('market', filters.market)
  if (filters.niche_id != null) params.set('niche_id', String(filters.niche_id))
  if (filters.status) params.set('status', filters.status)
  const qs = params.toString()
  return useApiQuery<Target[]>(['targets', filters], `/api/targets${qs ? `?${qs}` : ''}`)
}

export const useSaveTarget = () =>
  useApiMutation(
    ({ id, data }: { id?: string; data: Partial<TargetInput> }) =>
      id
        ? api<Target>(`/api/targets/${id}`, { method: 'PATCH', body: body(data) })
        : api<Target>('/api/targets', { method: 'POST', body: body(data) }),
    { invalidate: [['targets']], success: 'Target enregistree' },
  )

export const useBulkCreateTargets = () =>
  useApiMutation(
    (targets: TargetInput[]) =>
      api<Target[]>('/api/targets/bulk', { method: 'POST', body: body({ targets }) }),
    { invalidate: [['targets']], success: 'Targets importees' },
  )

export const useDeleteTarget = () =>
  useApiMutation((id: string) => api<void>(`/api/targets/${id}`, { method: 'DELETE' }), {
    invalidate: [['targets']],
    success: 'Target supprimee',
  })

// --- Presets (Comportements) -------------------------------------------------

export function usePresets(filters: PresetFilters = {}) {
  const params = new URLSearchParams()
  if (filters.plateforme) params.set('plateforme', filters.plateforme)
  if (filters.session_type) params.set('session_type', filters.session_type)
  const qs = params.toString()
  return useApiQuery<Preset[]>(['presets', filters], `/api/presets${qs ? `?${qs}` : ''}`)
}

export const useSavePreset = () =>
  useApiMutation(
    ({ id, data }: { id?: string; data: Partial<PresetInput> }) =>
      id
        ? api<Preset>(`/api/presets/${id}`, { method: 'PATCH', body: body(data) })
        : api<Preset>('/api/presets', { method: 'POST', body: body(data) }),
    { invalidate: [['presets']], success: 'Preset enregistre' },
  )

export const useDeletePreset = () =>
  useApiMutation((id: string) => api<void>(`/api/presets/${id}`, { method: 'DELETE' }), {
    invalidate: [['presets']],
    success: 'Preset supprime',
  })

// --- Logs --------------------------------------------------------------------

export function useEvents(filters: EventFilters = {}) {
  const params = new URLSearchParams()
  if (filters.module) params.set('module', filters.module)
  if (filters.level) params.set('level', filters.level)
  if (filters.target) params.set('target', filters.target)
  if (filters.limit) params.set('limit', String(filters.limit))
  if (filters.offset) params.set('offset', String(filters.offset))
  const qs = params.toString()
  return useApiQuery<LogEvent[]>(['events', filters], `/api/logs/events${qs ? `?${qs}` : ''}`)
}

export const useLogStats = () => useApiQuery<LogStats>(['logStats'], '/api/logs/stats')

export function useIncidents(filters: { module?: string; status?: string } = {}) {
  const params = new URLSearchParams()
  if (filters.module) params.set('module', filters.module)
  if (filters.status) params.set('status', filters.status)
  const qs = params.toString()
  return useApiQuery<Incident[]>(['incidents', filters], `/api/logs/incidents${qs ? `?${qs}` : ''}`)
}

export const useUpdateIncident = () =>
  useApiMutation(
    ({ id, status }: { id: string; status: string }) =>
      api<Incident>(`/api/logs/incidents/${id}`, { method: 'PATCH', body: body({ status }) }),
    { invalidate: [['incidents'], ['logStats']], success: 'Incident mis a jour' },
  )

export const useAlertRules = () =>
  useApiQuery<AlertRule[]>(['alertRules'], '/api/logs/rules')

export const useCreateAlertRule = () =>
  useApiMutation(
    (data: AlertRuleCreate) =>
      api<AlertRule>('/api/logs/rules', { method: 'POST', body: body(data) }),
    { invalidate: [['alertRules']], success: 'Regle creee' },
  )

export const useDeleteAlertRule = () =>
  useApiMutation((id: string) => api<void>(`/api/logs/rules/${id}`, { method: 'DELETE' }), {
    invalidate: [['alertRules']],
    success: 'Regle supprimee',
  })
