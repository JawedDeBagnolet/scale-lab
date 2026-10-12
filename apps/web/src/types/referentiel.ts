export interface Niche {
  id: number
  label: string
}

export interface Marche {
  code: string
  label: string
  actif: boolean
  langue: string | null
  fuseau: string | null
}
