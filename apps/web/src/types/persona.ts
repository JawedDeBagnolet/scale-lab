import type { CompteStatus, CompteWorkflow, Platform } from './compte'

export interface PersonaBio {
  platform: Platform
  text: string
}

export interface PersonaTelegram {
  bot?: string
  username?: string
  chat_id?: string
  langue?: string
  groupe?: string
  topic?: string
}

export interface PersonaCompte {
  id: string
  handle: string
  plateforme: Platform
  workflow: CompteWorkflow
  status: CompteStatus
}

export interface PersonaInput {
  first_name: string
  last_name: string | null
  color: string | null
  market: string | null
  city: string | null
  age: number | null
  platforms: Platform[] | null
  niches: number[] | null
  bios: PersonaBio[] | null
  prompt: string | null
  funnel: string | null
  telegram: PersonaTelegram | null
  photo_url: string | null
  prs_id: string | null
}

export interface Persona extends PersonaInput {
  id: string
  created_at: string
  updated_at: string
  comptes: PersonaCompte[]
}
