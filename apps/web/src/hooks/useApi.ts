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
import type { Proxy, ProxyFilters, ProxyInput } from '../types/proxy'
import type { DailyStat, StatFilters, StatsOverview } from '../types/statistique'
import type { Target, TargetFilters, TargetInput } from '../types/target'
import type { IPhone, IPhoneFilters, IPhoneInput, Telemetry } from '../types/iphone'
import type { CrmOverview, Fan, FanFilters, FanInput, Script, ScriptFilters, ScriptInput, Transaction, TransactionFilters, TransactionInput } from '../types/crm'
import type {
  Album,
  AlbumFilters,
  AlbumInput,
  Favorite,
  FavoriteFilters,
  FavoriteInput,
  Inspiration,
  InspirationFilters,
  Snipe,
  SnipeFilters,
  SnipeInput,
  VeilleOverview,
  VeilleSource,
  VeilleSourceFilters,
  VeilleSourceInput,
} from '../types/veille'
import type { Domain, DomainInput, LinkFilters, LinkStats, TrackedLink, LinkInput } from '../types/lien'
import type {
  Scenario,
  ScenarioInput,
  ScenarioFilters,
  Run,
  RunInput,
  RunFilters,
  PlageHoraire,
  PlageHoraireInput,
  ScenariosOverview,
} from '../types/scenario'
import type {
  Collection,
  CollectionInput,
  CollectionFilters,
  PostingMedia,
  MediaFilters,
  PostingTemplate,
  TemplateFilters,
  Campagne,
  CampagneInput,
  CampagneFilters,
  Publication,
  PublicationInput,
  PublicationFilters,
  PostingOverview,
} from '../types/posting'

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

// --- Proxies -----------------------------------------------------------------

export function useProxies(filters: ProxyFilters = {}) {
  const params = new URLSearchParams()
  if (filters.pool) params.set('pool', filters.pool)
  if (filters.status) params.set('status', filters.status)
  if (filters.country) params.set('country', filters.country)
  const qs = params.toString()
  return useApiQuery<Proxy[]>(['proxies', filters], `/api/proxies${qs ? `?${qs}` : ''}`)
}

export const useSaveProxy = () =>
  useApiMutation(
    ({ id, data }: { id?: string; data: Partial<ProxyInput> }) =>
      id
        ? api<Proxy>(`/api/proxies/${id}`, { method: 'PATCH', body: body(data) })
        : api<Proxy>('/api/proxies', { method: 'POST', body: body(data) }),
    { invalidate: [['proxies']], success: 'Proxy enregistre' },
  )

export const useDeleteProxy = () =>
  useApiMutation((id: string) => api<void>(`/api/proxies/${id}`, { method: 'DELETE' }), {
    invalidate: [['proxies']],
    success: 'Proxy supprime',
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

// --- iPhones (Parc iPhone) ---------------------------------------------------

export function useIphones(filters: IPhoneFilters = {}) {
  const params = new URLSearchParams()
  if (filters.status) params.set('status', filters.status)
  if (filters.market) params.set('market', filters.market)
  const qs = params.toString()
  return useApiQuery<IPhone[]>(['iphones', filters], `/api/iphones${qs ? `?${qs}` : ''}`)
}

export const useSaveIphone = () =>
  useApiMutation(
    ({ id, data }: { id?: string; data: Partial<IPhoneInput> }) =>
      id
        ? api<IPhone>(`/api/iphones/${id}`, { method: 'PATCH', body: body(data) })
        : api<IPhone>('/api/iphones', { method: 'POST', body: body(data) }),
    { invalidate: [['iphones']], success: 'iPhone enregistre' },
  )

export const useDeleteIphone = () =>
  useApiMutation((id: string) => api<void>(`/api/iphones/${id}`, { method: 'DELETE' }), {
    invalidate: [['iphones']],
    success: 'iPhone supprime',
  })

export const useUpdateTelemetry = () =>
  useApiMutation(
    ({ id, data }: { id: string; data: Partial<Telemetry> }) =>
      api<IPhone>(`/api/iphones/${id}/telemetry`, { method: 'PATCH', body: body(data) }),
    { invalidate: [['iphones']], success: 'Telemetrie mise a jour' },
  )

// --- Statistiques --------------------------------------------------------------

export function useStats(filters: StatFilters) {
  const params = new URLSearchParams()
  params.set('compte_id', filters.compte_id)
  if (filters.date_from) params.set('date_from', filters.date_from)
  if (filters.date_to) params.set('date_to', filters.date_to)
  const qs = params.toString()
  return useApiQuery<DailyStat[]>(
    ['stats', filters],
    `/api/stats?${qs}`,
  )
}

export function useStatsOverview(compte_id: string | undefined) {
  return useQuery({
    queryKey: ['statsOverview', compte_id],
    queryFn: () => api<StatsOverview>(`/api/stats/overview?compte_id=${compte_id}`),
    enabled: !!compte_id,
  })
}

export const useBulkCreateStats = () =>
  useApiMutation(
    (stats: DailyStat[]) =>
      api<DailyStat[]>('/api/stats/bulk', { method: 'POST', body: body({ stats }) }),
    { invalidate: [['stats'], ['statsOverview']], success: 'Stats importees' },
  )

// --- Liens -------------------------------------------------------------------

export function useLinks(filters: LinkFilters = {}) {
  const params = new URLSearchParams()
  if (filters.domain_id) params.set('domain_id', filters.domain_id)
  if (filters.plateforme) params.set('plateforme', filters.plateforme)
  if (filters.active != null) params.set('active', String(filters.active))
  const qs = params.toString()
  return useApiQuery<TrackedLink[]>(['links', filters], `/api/liens${qs ? `?${qs}` : ''}`)
}

export const useSaveLink = () =>
  useApiMutation(
    ({ id, data }: { id?: string; data: Partial<LinkInput> }) =>
      id
        ? api<TrackedLink>(`/api/liens/${id}`, { method: 'PATCH', body: body(data) })
        : api<TrackedLink>('/api/liens', { method: 'POST', body: body(data) }),
    { invalidate: [['links']], success: 'Lien enregistre' },
  )

export const useDeleteLink = () =>
  useApiMutation((id: string) => api<void>(`/api/liens/${id}`, { method: 'DELETE' }), {
    invalidate: [['links']],
    success: 'Lien supprime',
  })

export function useLinkStats(id: string | undefined) {
  return useQuery({
    queryKey: ['linkStats', id],
    queryFn: () => api<LinkStats>(`/api/liens/${id}/stats`),
    enabled: !!id,
  })
}

export const useDomains = () =>
  useApiQuery<Domain[]>(['domains'], '/api/liens/domains')

export const useSaveDomain = () =>
  useApiMutation(
    ({ id, data }: { id?: string; data: Partial<DomainInput> }) =>
      id
        ? api<Domain>(`/api/liens/domains/${id}`, { method: 'PATCH', body: body(data) })
        : api<Domain>('/api/liens/domains', { method: 'POST', body: body(data) }),
    { invalidate: [['domains']], success: 'Domaine enregistre' },
  )

export const useDeleteDomain = () =>
  useApiMutation((id: string) => api<void>(`/api/liens/domains/${id}`, { method: 'DELETE' }), {
    invalidate: [['domains']],
    success: 'Domaine supprime',
  })

// --- Veille ------------------------------------------------------------------

export const useVeilleOverview = () =>
  useApiQuery<VeilleOverview>(['veilleOverview'], '/api/veille/overview')

export function useVeilleSources(filters: VeilleSourceFilters = {}) {
  const params = new URLSearchParams()
  if (filters.plateforme) params.set('plateforme', filters.plateforme)
  if (filters.niche_id != null) params.set('niche_id', String(filters.niche_id))
  if (filters.active != null) params.set('active', String(filters.active))
  const qs = params.toString()
  return useApiQuery<VeilleSource[]>(['veilleSources', filters], `/api/veille/sources${qs ? `?${qs}` : ''}`)
}

export const useSaveSource = () =>
  useApiMutation(
    ({ id, data }: { id?: string; data: Partial<VeilleSourceInput> }) =>
      id
        ? api<VeilleSource>(`/api/veille/sources/${id}`, { method: 'PATCH', body: body(data) })
        : api<VeilleSource>('/api/veille/sources', { method: 'POST', body: body(data) }),
    { invalidate: [['veilleSources'], ['veilleOverview']], success: 'Source enregistree' },
  )

export const useDeleteSource = () =>
  useApiMutation((id: string) => api<void>(`/api/veille/sources/${id}`, { method: 'DELETE' }), {
    invalidate: [['veilleSources'], ['veilleOverview']],
    success: 'Source supprimee',
  })

export function useInspirations(filters: InspirationFilters = {}) {
  const params = new URLSearchParams()
  if (filters.source_id) params.set('source_id', filters.source_id)
  if (filters.status) params.set('status', filters.status)
  if (filters.media_type) params.set('media_type', filters.media_type)
  const qs = params.toString()
  return useApiQuery<Inspiration[]>(['inspirations', filters], `/api/veille/inspirations${qs ? `?${qs}` : ''}`)
}

export const useUpdateInspiration = () =>
  useApiMutation(
    ({ id, data }: { id: string; data: Partial<Inspiration> }) =>
      api<Inspiration>(`/api/veille/inspirations/${id}`, { method: 'PATCH', body: body(data) }),
    { invalidate: [['inspirations'], ['veilleOverview']], success: 'Inspiration mise a jour' },
  )

export function useFavorites(filters: FavoriteFilters = {}) {
  const params = new URLSearchParams()
  if (filters.album_id) params.set('album_id', filters.album_id)
  const qs = params.toString()
  return useApiQuery<Favorite[]>(['favorites', filters], `/api/veille/favorites${qs ? `?${qs}` : ''}`)
}

export const useAddFavorite = () =>
  useApiMutation(
    (data: FavoriteInput) =>
      api<Favorite>('/api/veille/favorites', { method: 'POST', body: body(data) }),
    { invalidate: [['favorites'], ['veilleOverview']], success: 'Favori ajoute' },
  )

export const useRemoveFavorite = () =>
  useApiMutation((id: string) => api<void>(`/api/veille/favorites/${id}`, { method: 'DELETE' }), {
    invalidate: [['favorites']],
    success: 'Favori retire',
  })

export function useSnipes(filters: SnipeFilters = {}) {
  const params = new URLSearchParams()
  if (filters.status) params.set('status', filters.status)
  if (filters.priority) params.set('priority', filters.priority)
  if (filters.persona_id) params.set('persona_id', filters.persona_id)
  const qs = params.toString()
  return useApiQuery<Snipe[]>(['snipes', filters], `/api/veille/snipes${qs ? `?${qs}` : ''}`)
}

export const useSaveSnipe = () =>
  useApiMutation(
    ({ id, data }: { id?: string; data: Partial<SnipeInput> }) =>
      id
        ? api<Snipe>(`/api/veille/snipes/${id}`, { method: 'PATCH', body: body(data) })
        : api<Snipe>('/api/veille/snipes', { method: 'POST', body: body(data) }),
    { invalidate: [['snipes'], ['veilleOverview']], success: 'Snipe enregistre' },
  )

export function useAlbums(filters: AlbumFilters = {}) {
  const params = new URLSearchParams()
  if (filters.persona_id) params.set('persona_id', filters.persona_id)
  const qs = params.toString()
  return useApiQuery<Album[]>(['albums', filters], `/api/veille/albums${qs ? `?${qs}` : ''}`)
}

export const useSaveAlbum = () =>
  useApiMutation(
    ({ id, data }: { id?: string; data: Partial<AlbumInput> }) =>
      id
        ? api<Album>(`/api/veille/albums/${id}`, { method: 'PATCH', body: body(data) })
        : api<Album>('/api/veille/albums', { method: 'POST', body: body(data) }),
    { invalidate: [['albums'], ['veilleOverview']], success: 'Album enregistre' },
  )

export const useDeleteAlbum = () =>
  useApiMutation((id: string) => api<void>(`/api/veille/albums/${id}`, { method: 'DELETE' }), {
    invalidate: [['albums'], ['veilleOverview']],
    success: 'Album supprime',
  })

// --- CRM ---------------------------------------------------------------------

export const useCrmOverview = () =>
  useApiQuery<CrmOverview>(['crmOverview'], '/api/crm/overview')

export function useFans(filters: FanFilters = {}) {
  const params = new URLSearchParams()
  if (filters.creator_id) params.set('creator_id', filters.creator_id)
  if (filters.platform_origin) params.set('platform_origin', filters.platform_origin)
  const qs = params.toString()
  return useApiQuery<Fan[]>(['fans', filters], `/api/crm/fans${qs ? `?${qs}` : ''}`)
}

export const useSaveFan = () =>
  useApiMutation(
    ({ id, data }: { id?: string; data: Partial<FanInput> }) =>
      id
        ? api<Fan>(`/api/crm/fans/${id}`, { method: 'PATCH', body: body(data) })
        : api<Fan>('/api/crm/fans', { method: 'POST', body: body(data) }),
    { invalidate: [['fans'], ['crmOverview']], success: 'Fan enregistre' },
  )

export function useTransactions(filters: TransactionFilters = {}) {
  const params = new URLSearchParams()
  if (filters.fan_id) params.set('fan_id', filters.fan_id)
  if (filters.creator_id) params.set('creator_id', filters.creator_id)
  if (filters.type) params.set('type', filters.type)
  if (filters.date_from) params.set('date_from', filters.date_from)
  if (filters.date_to) params.set('date_to', filters.date_to)
  const qs = params.toString()
  return useApiQuery<Transaction[]>(['transactions', filters], `/api/crm/transactions${qs ? `?${qs}` : ''}`)
}

export const useCreateTransaction = () =>
  useApiMutation(
    (data: TransactionInput) =>
      api<Transaction>('/api/crm/transactions', { method: 'POST', body: body(data) }),
    { invalidate: [['transactions'], ['crmOverview']], success: 'Transaction enregistree' },
  )

export function useScripts(filters: ScriptFilters = {}) {
  const params = new URLSearchParams()
  if (filters.active != null) params.set('active', String(filters.active))
  if (filters.folder) params.set('folder', filters.folder)
  const qs = params.toString()
  return useApiQuery<Script[]>(['scripts', filters], `/api/crm/scripts${qs ? `?${qs}` : ''}`)
}

export const useSaveScript = () =>
  useApiMutation(
    ({ id, data }: { id?: string; data: Partial<ScriptInput> }) =>
      id
        ? api<Script>(`/api/crm/scripts/${id}`, { method: 'PATCH', body: body(data) })
        : api<Script>('/api/crm/scripts', { method: 'POST', body: body(data) }),
    { invalidate: [['scripts'], ['crmOverview']], success: 'Script enregistre' },
  )

export const useDeleteScript = () =>
  useApiMutation((id: string) => api<void>(`/api/crm/scripts/${id}`, { method: 'DELETE' }), {
    invalidate: [['scripts'], ['crmOverview']],
    success: 'Script supprime',
  })

// --- Scenarios ---------------------------------------------------------------

export const useScenariosOverview = () =>
  useApiQuery<ScenariosOverview>(['scenariosOverview'], '/api/scenarios/overview')

export function useScenariosList(filters: ScenarioFilters = {}) {
  const params = new URLSearchParams()
  if (filters.origin) params.set('origin', filters.origin)
  if (filters.plateforme) params.set('plateforme', filters.plateforme)
  if (filters.active != null) params.set('active', String(filters.active))
  const qs = params.toString()
  return useApiQuery<Scenario[]>(['scenarios', filters], `/api/scenarios${qs ? `?${qs}` : ''}`)
}

export const useSaveScenario = () =>
  useApiMutation(
    ({ id, data }: { id?: string; data: Partial<ScenarioInput> }) =>
      id
        ? api<Scenario>(`/api/scenarios/${id}`, { method: 'PATCH', body: body(data) })
        : api<Scenario>('/api/scenarios', { method: 'POST', body: body(data) }),
    { invalidate: [['scenarios'], ['scenariosOverview']], success: 'Scenario enregistre' },
  )

export const useDeleteScenario = () =>
  useApiMutation((id: string) => api<void>(`/api/scenarios/${id}`, { method: 'DELETE' }), {
    invalidate: [['scenarios'], ['scenariosOverview']],
    success: 'Scenario supprime',
  })

export function useRuns(filters: RunFilters = {}) {
  const params = new URLSearchParams()
  if (filters.scenario_id) params.set('scenario_id', filters.scenario_id)
  if (filters.status) params.set('status', filters.status)
  const qs = params.toString()
  return useApiQuery<Run[]>(['runs', filters], `/api/scenarios/runs/list${qs ? `?${qs}` : ''}`)
}

export const useSaveRun = () =>
  useApiMutation(
    ({ id, data }: { id?: string; data: Partial<RunInput> }) =>
      id
        ? api<Run>(`/api/scenarios/runs/${id}`, { method: 'PATCH', body: body(data) })
        : api<Run>('/api/scenarios/runs', { method: 'POST', body: body(data) }),
    { invalidate: [['runs'], ['scenariosOverview']], success: 'Execution enregistree' },
  )

export const useDeleteRun = () =>
  useApiMutation((id: string) => api<void>(`/api/scenarios/runs/${id}`, { method: 'DELETE' }), {
    invalidate: [['runs'], ['scenariosOverview']],
    success: 'Execution supprimee',
  })

export const usePlages = () =>
  useApiQuery<PlageHoraire[]>(['plages'], '/api/scenarios/plages')

export const useSavePlage = () =>
  useApiMutation(
    ({ id, data }: { id?: string; data: Partial<PlageHoraireInput> }) =>
      id
        ? api<PlageHoraire>(`/api/scenarios/plages/${id}`, { method: 'PATCH', body: body(data) })
        : api<PlageHoraire>('/api/scenarios/plages', { method: 'POST', body: body(data) }),
    { invalidate: [['plages'], ['scenariosOverview']], success: 'Plage horaire enregistree' },
  )

export const useDeletePlage = () =>
  useApiMutation((id: string) => api<void>(`/api/scenarios/plages/${id}`, { method: 'DELETE' }), {
    invalidate: [['plages'], ['scenariosOverview']],
    success: 'Plage horaire supprimee',
  })

// --- Posting -----------------------------------------------------------------

export const usePostingOverview = () =>
  useApiQuery<PostingOverview>(['postingOverview'], '/api/posting/overview')

export function useCollections(filters: CollectionFilters = {}) {
  const params = new URLSearchParams()
  if (filters.persona_id) params.set('persona_id', filters.persona_id)
  if (filters.plateforme) params.set('plateforme', filters.plateforme)
  if (filters.collection_type) params.set('collection_type', filters.collection_type)
  const qs = params.toString()
  return useApiQuery<Collection[]>(['collections', filters], `/api/posting/collections${qs ? `?${qs}` : ''}`)
}

export const useSaveCollection = () =>
  useApiMutation(
    ({ id, data }: { id?: string; data: Partial<CollectionInput> }) =>
      id
        ? api<Collection>(`/api/posting/collections/${id}`, { method: 'PATCH', body: body(data) })
        : api<Collection>('/api/posting/collections', { method: 'POST', body: body(data) }),
    { invalidate: [['collections'], ['postingOverview']], success: 'Collection enregistree' },
  )

export const useDeleteCollection = () =>
  useApiMutation((id: string) => api<void>(`/api/posting/collections/${id}`, { method: 'DELETE' }), {
    invalidate: [['collections'], ['postingOverview']],
    success: 'Collection supprimee',
  })

export function usePostingMedias(filters: MediaFilters = {}) {
  const params = new URLSearchParams()
  if (filters.persona_id) params.set('persona_id', filters.persona_id)
  if (filters.media_type) params.set('media_type', filters.media_type)
  if (filters.folder) params.set('folder', filters.folder)
  if (filters.used != null) params.set('used', String(filters.used))
  const qs = params.toString()
  return useApiQuery<PostingMedia[]>(['postingMedias', filters], `/api/posting/medias${qs ? `?${qs}` : ''}`)
}

export function usePostingTemplates(filters: TemplateFilters = {}) {
  const params = new URLSearchParams()
  if (filters.persona_id) params.set('persona_id', filters.persona_id)
  if (filters.plateforme) params.set('plateforme', filters.plateforme)
  if (filters.template_type) params.set('template_type', filters.template_type)
  const qs = params.toString()
  return useApiQuery<PostingTemplate[]>(['postingTemplates', filters], `/api/posting/templates${qs ? `?${qs}` : ''}`)
}

export function useCampagnes(filters: CampagneFilters = {}) {
  const params = new URLSearchParams()
  if (filters.persona_id) params.set('persona_id', filters.persona_id)
  if (filters.plateforme) params.set('plateforme', filters.plateforme)
  if (filters.status) params.set('status', filters.status)
  const qs = params.toString()
  return useApiQuery<Campagne[]>(['campagnes', filters], `/api/posting/campagnes${qs ? `?${qs}` : ''}`)
}

export const useSaveCampagne = () =>
  useApiMutation(
    ({ id, data }: { id?: string; data: Partial<CampagneInput> }) =>
      id
        ? api<Campagne>(`/api/posting/campagnes/${id}`, { method: 'PATCH', body: body(data) })
        : api<Campagne>('/api/posting/campagnes', { method: 'POST', body: body(data) }),
    { invalidate: [['campagnes'], ['postingOverview']], success: 'Campagne enregistree' },
  )

export const useDeleteCampagne = () =>
  useApiMutation((id: string) => api<void>(`/api/posting/campagnes/${id}`, { method: 'DELETE' }), {
    invalidate: [['campagnes'], ['postingOverview']],
    success: 'Campagne supprimee',
  })

export function usePublications(filters: PublicationFilters = {}) {
  const params = new URLSearchParams()
  if (filters.compte_id) params.set('compte_id', filters.compte_id)
  if (filters.campagne_id) params.set('campagne_id', filters.campagne_id)
  if (filters.status) params.set('status', filters.status)
  const qs = params.toString()
  return useApiQuery<Publication[]>(['publications', filters], `/api/posting/publications${qs ? `?${qs}` : ''}`)
}

export const useSavePublication = () =>
  useApiMutation(
    ({ id, data }: { id?: string; data: Partial<PublicationInput> }) =>
      id
        ? api<Publication>(`/api/posting/publications/${id}`, { method: 'PATCH', body: body(data) })
        : api<Publication>('/api/posting/publications', { method: 'POST', body: body(data) }),
    { invalidate: [['publications'], ['postingOverview']], success: 'Publication enregistree' },
  )

export const useDeletePublication = () =>
  useApiMutation((id: string) => api<void>(`/api/posting/publications/${id}`, { method: 'DELETE' }), {
    invalidate: [['publications'], ['postingOverview']],
    success: 'Publication supprimee',
  })
