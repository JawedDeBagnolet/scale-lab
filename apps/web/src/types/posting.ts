export const COLLECTION_TYPES = ['assembled', 'variable'] as const
export type CollectionType = (typeof COLLECTION_TYPES)[number]

export const MEDIA_TYPES = ['image', 'video', 'audio'] as const
export type MediaType = (typeof MEDIA_TYPES)[number]

export const TEMPLATE_TYPES = ['post', 'story'] as const
export type TemplateType = (typeof TEMPLATE_TYPES)[number]

export const CAMPAGNE_STATUSES = ['draft', 'active', 'paused', 'done'] as const
export type CampagneStatus = (typeof CAMPAGNE_STATUSES)[number]

export const PUBLICATION_STATUSES = ['planned', 'published', 'failed', 'suspended'] as const
export type PublicationStatus = (typeof PUBLICATION_STATUSES)[number]

export interface Collection {
  id: string
  name: string
  collection_type: CollectionType
  persona_id: string | null
  plateforme: string | null
  post_type: string | null
  captions: string[]
  media_ids: string[]
  created_at: string
  updated_at: string
}

export interface CollectionInput {
  name: string
  collection_type: CollectionType
  persona_id?: string | null
  plateforme?: string | null
  post_type?: string | null
  captions?: string[]
  media_ids?: string[]
}

export interface CollectionFilters {
  persona_id?: string
  plateforme?: string
  collection_type?: string
}

export interface PostingMedia {
  id: string
  persona_id: string | null
  media_type: MediaType
  url: string
  duration: number | null
  tags: string[]
  folder: string | null
  used: boolean
  created_at: string
}

export interface MediaInput {
  persona_id?: string | null
  media_type: MediaType
  url: string
  duration?: number | null
  tags?: string[]
  folder?: string | null
  used?: boolean
}

export interface MediaFilters {
  persona_id?: string
  media_type?: string
  folder?: string
  used?: boolean
}

export interface PostingTemplate {
  id: string
  name: string
  persona_id: string | null
  plateforme: string | null
  template_type: TemplateType
  layers: Record<string, unknown>[]
  variables: Record<string, unknown> | null
  collection_id: string | null
  created_at: string
  updated_at: string
}

export interface TemplateInput {
  name: string
  persona_id?: string | null
  plateforme?: string | null
  template_type?: TemplateType
  layers?: Record<string, unknown>[]
  variables?: Record<string, unknown> | null
  collection_id?: string | null
}

export interface TemplateFilters {
  persona_id?: string
  plateforme?: string
  template_type?: string
}

export interface Campagne {
  id: string
  name: string
  icon: string | null
  persona_id: string | null
  plateforme: string | null
  status: CampagneStatus
  scenarios: string[]
  waves: Record<string, unknown>[]
  planning: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface CampagneInput {
  name: string
  icon?: string | null
  persona_id?: string | null
  plateforme?: string | null
  status?: CampagneStatus
  scenarios?: string[]
  waves?: Record<string, unknown>[]
  planning?: Record<string, unknown> | null
}

export interface CampagneFilters {
  persona_id?: string
  plateforme?: string
  status?: string
}

export interface Publication {
  id: string
  compte_id: string
  campagne_id: string | null
  media_id: string | null
  caption: string | null
  scheduled_at: string | null
  status: PublicationStatus
  platform_post_id: string | null
  created_at: string
  updated_at: string
}

export interface PublicationInput {
  compte_id: string
  campagne_id?: string | null
  media_id?: string | null
  caption?: string | null
  scheduled_at?: string | null
  status?: PublicationStatus
  platform_post_id?: string | null
}

export interface PublicationFilters {
  compte_id?: string
  campagne_id?: string
  status?: string
}

export interface PostingOverview {
  total_collections: number
  total_medias: number
  total_templates: number
  total_campagnes: number
  active_campagnes: number
  total_publications: number
  published: number
  planned: number
  failed: number
}
