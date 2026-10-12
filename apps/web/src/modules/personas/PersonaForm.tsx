import { useState, type FormEvent } from 'react'
import Modal from '../../components/Modal'
import { PLATFORM_META } from '../../components/PlatformBadge'
import { useMarches, useNiches, useSavePersona } from '../../hooks/useApi'
import { PLATFORMS, type Platform } from '../../types/compte'
import type { Persona, PersonaInput, PersonaTelegram } from '../../types/persona'

const COLORS = ['#6d5ef0', '#4b7bf5', '#22c55e', '#f59e0b', '#ef4444', '#ec4899', '#14b8a6', '#a855f7']

const TELEGRAM_FIELDS: { key: keyof PersonaTelegram; label: string; placeholder: string }[] = [
  { key: 'bot', label: 'Bot', placeholder: '@lena_bot' },
  { key: 'username', label: 'Username de la modele', placeholder: '@lena' },
  { key: 'chat_id', label: 'Chat ID', placeholder: '-1001234567890' },
  { key: 'langue', label: 'Langue des briefs', placeholder: 'fr' },
  { key: 'groupe', label: 'Groupe de production', placeholder: '-1009876543210' },
  { key: 'topic', label: 'Topic', placeholder: '12' },
]

interface FormState {
  first_name: string
  last_name: string
  color: string
  market: string
  city: string
  age: string
  platforms: Platform[]
  niches: number[]
  bios: Record<Platform, string>
  prompt: string
  funnel: string
  telegram: Record<keyof PersonaTelegram, string>
  photo_url: string
  prs_id: string
}

function toState(p?: Persona): FormState {
  const bios: Record<Platform, string> = { ig: '', th: '', x: '' }
  p?.bios?.forEach((b) => {
    if (b.platform in bios) bios[b.platform] = b.text ?? ''
  })
  const tg = p?.telegram ?? {}
  return {
    first_name: p?.first_name ?? '',
    last_name: p?.last_name ?? '',
    color: p?.color ?? COLORS[0],
    market: p?.market ?? '',
    city: p?.city ?? '',
    age: p?.age != null ? String(p.age) : '',
    platforms: p?.platforms ?? [],
    niches: p?.niches ?? [],
    bios,
    prompt: p?.prompt ?? '',
    funnel: p?.funnel ?? '',
    telegram: {
      bot: tg.bot ?? '',
      username: tg.username ?? '',
      chat_id: tg.chat_id ?? '',
      langue: tg.langue ?? '',
      groupe: tg.groupe ?? '',
      topic: tg.topic ?? '',
    },
    photo_url: p?.photo_url ?? '',
    prs_id: p?.prs_id ?? '',
  }
}

const orNull = (s: string) => s.trim() || null

function toPayload(s: FormState): PersonaInput {
  const telegram: PersonaTelegram = {}
  TELEGRAM_FIELDS.forEach(({ key }) => {
    const v = s.telegram[key].trim()
    if (v) telegram[key] = v
  })
  return {
    first_name: s.first_name.trim(),
    last_name: orNull(s.last_name),
    color: s.color,
    market: orNull(s.market),
    city: orNull(s.city),
    age: s.age ? Number(s.age) : null,
    platforms: s.platforms,
    niches: s.niches,
    bios: s.platforms
      .filter((p) => s.bios[p].trim())
      .map((p) => ({ platform: p, text: s.bios[p].trim() })),
    prompt: orNull(s.prompt),
    funnel: orNull(s.funnel),
    telegram,
    photo_url: orNull(s.photo_url),
    prs_id: orNull(s.prs_id),
  }
}

function toggle<T>(list: T[], item: T): T[] {
  return list.includes(item) ? list.filter((x) => x !== item) : [...list, item]
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-6 last:mb-0">
      <h3 className="mb-3 text-[13px] font-bold">{title}</h3>
      {children}
    </section>
  )
}

export default function PersonaForm({ persona, onClose }: { persona?: Persona; onClose: () => void }) {
  const [s, setS] = useState<FormState>(() => toState(persona))
  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => setS((prev) => ({ ...prev, [key]: value }))

  const niches = useNiches()
  const marches = useMarches()
  const save = useSavePersona()

  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate({ id: persona?.id, data: toPayload(s) }, { onSuccess: onClose })
  }

  return (
    <form onSubmit={submit}>
      <Modal
        title={persona ? `Modifier ${persona.first_name}` : 'Nouvelle persona'}
        onClose={onClose}
        footer={
          <>
            <button type="button" className="btn btn-ghost" onClick={onClose}>
              Annuler
            </button>
            <button type="submit" className="btn btn-primary" disabled={save.isPending || !s.first_name.trim()}>
              {save.isPending ? 'Enregistrement...' : 'Enregistrer'}
            </button>
          </>
        }
      >
        <Section title="Identite">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label" htmlFor="pf-first">Prenom *</label>
              <input id="pf-first" className="field" required maxLength={100} autoFocus
                value={s.first_name} onChange={(e) => set('first_name', e.target.value)} />
            </div>
            <div>
              <label className="label" htmlFor="pf-last">Nom</label>
              <input id="pf-last" className="field" maxLength={100}
                value={s.last_name} onChange={(e) => set('last_name', e.target.value)} />
            </div>
            <div>
              <label className="label" htmlFor="pf-market">Marche</label>
              <select id="pf-market" className="field" value={s.market} onChange={(e) => set('market', e.target.value)}>
                <option value="">Aucun</option>
                {marches.data?.map((m) => (
                  <option key={m.code} value={m.code}>{m.code} · {m.label}</option>
                ))}
              </select>
            </div>
            <div className="grid grid-cols-[1fr_96px] gap-4">
              <div>
                <label className="label" htmlFor="pf-city">Ville</label>
                <input id="pf-city" className="field" maxLength={100}
                  value={s.city} onChange={(e) => set('city', e.target.value)} />
              </div>
              <div>
                <label className="label" htmlFor="pf-age">Age</label>
                <input id="pf-age" className="field" type="number" min={18} max={99}
                  value={s.age} onChange={(e) => set('age', e.target.value)} />
              </div>
            </div>
            <div>
              <span className="label">Couleur</span>
              <div className="flex h-[38px] items-center gap-2">
                {COLORS.map((c) => (
                  <button key={c} type="button" aria-label={`Couleur ${c}`} onClick={() => set('color', c)}
                    className="h-6 w-6 cursor-pointer rounded-full transition-transform hover:scale-110"
                    style={{ background: c, outline: s.color === c ? '2px solid #fff' : 'none', outlineOffset: 2 }} />
                ))}
              </div>
            </div>
            <div>
              <label className="label" htmlFor="pf-prs">ID OnlyChat (prsId)</label>
              <input id="pf-prs" className="field" maxLength={100}
                value={s.prs_id} onChange={(e) => set('prs_id', e.target.value)} />
            </div>
            <div className="col-span-2">
              <label className="label" htmlFor="pf-photo">URL de la photo</label>
              <input id="pf-photo" className="field" type="url" placeholder="https://..."
                value={s.photo_url} onChange={(e) => set('photo_url', e.target.value)} />
            </div>
          </div>
        </Section>

        <Section title="Plateformes et bios">
          <div className="mb-3 flex gap-2">
            {PLATFORMS.map((p) => {
              const IconCmp = PLATFORM_META[p].icon
              return (
                <button key={p} type="button" aria-pressed={s.platforms.includes(p)}
                  className={`chip ${s.platforms.includes(p) ? 'chip-on' : ''}`}
                  onClick={() => set('platforms', PLATFORMS.filter((x) => toggle(s.platforms, p).includes(x)))}>
                  <IconCmp size={14} /> {PLATFORM_META[p].label}
                </button>
              )
            })}
          </div>
          <div className="grid gap-3">
            {s.platforms.map((p) => (
              <div key={p}>
                <label className="label" htmlFor={`pf-bio-${p}`}>Bio {PLATFORM_META[p].label}</label>
                <textarea id={`pf-bio-${p}`} className="field" rows={2}
                  value={s.bios[p]} onChange={(e) => set('bios', { ...s.bios, [p]: e.target.value })} />
              </div>
            ))}
          </div>
        </Section>

        <Section title="Niches">
          <div className="flex flex-wrap gap-2">
            {niches.data?.map((n) => (
              <button key={n.id} type="button" aria-pressed={s.niches.includes(n.id)}
                className={`chip ${s.niches.includes(n.id) ? 'chip-on' : ''}`}
                onClick={() => set('niches', toggle(s.niches, n.id))}>
                {n.label}
              </button>
            ))}
            {niches.isLoading && <span className="text-xs text-dim">Chargement...</span>}
            {niches.isError && <span className="text-xs text-error">Niches indisponibles</span>}
          </div>
        </Section>

        <Section title="IA et funnel">
          <div className="grid gap-4">
            <div>
              <label className="label" htmlFor="pf-prompt">Prompt IA</label>
              <textarea id="pf-prompt" className="field" rows={4}
                value={s.prompt} onChange={(e) => set('prompt', e.target.value)} />
            </div>
            <div>
              <label className="label" htmlFor="pf-funnel">Funnel</label>
              <textarea id="pf-funnel" className="field" rows={2}
                value={s.funnel} onChange={(e) => set('funnel', e.target.value)} />
            </div>
          </div>
        </Section>

        <Section title="Telegram">
          <div className="grid grid-cols-3 gap-4">
            {TELEGRAM_FIELDS.map(({ key, label, placeholder }) => (
              <div key={key}>
                <label className="label" htmlFor={`pf-tg-${key}`}>{label}</label>
                <input id={`pf-tg-${key}`} className="field" placeholder={placeholder}
                  value={s.telegram[key]}
                  onChange={(e) => set('telegram', { ...s.telegram, [key]: e.target.value })} />
              </div>
            ))}
          </div>
        </Section>
      </Modal>
    </form>
  )
}
