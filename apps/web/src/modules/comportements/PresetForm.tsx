import { useState } from 'react'
import { FloppyDisk } from '@phosphor-icons/react'
import Modal from '../../components/Modal'
import { PLATFORM_META } from '../../components/PlatformBadge'
import { useSavePreset } from '../../hooks/useApi'
import { PLATFORMS, type Platform } from '../../types/compte'
import {
  SESSION_TYPES,
  SESSION_TYPE_LABELS,
  type Preset,
  type PresetConfig,
  type PresetInput,
  type SessionType,
} from '../../types/preset'

interface PresetFormProps {
  preset?: Preset
  onClose: () => void
}

const DEFAULT_CONFIG: PresetConfig = {
  probabilities: { like: 0.7, comment: 0.15, follow: 0.1, story_view: 0.8 },
  pauses: { min: 2, max: 8 },
  durations: { min: 15, max: 45 },
}

function NumberField({
  label,
  value,
  onChange,
  min = 0,
  max = 100,
  step = 1,
}: {
  label: string
  value: number
  onChange: (v: number) => void
  min?: number
  max?: number
  step?: number
}) {
  return (
    <div>
      <label className="label">{label}</label>
      <input
        type="number"
        className="field"
        value={value}
        min={min}
        max={max}
        step={step}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </div>
  )
}

function ProbabilitySlider({
  label,
  value,
  onChange,
}: {
  label: string
  value: number
  onChange: (v: number) => void
}) {
  return (
    <div className="flex items-center gap-3">
      <span className="w-24 text-xs font-medium capitalize">{label}</span>
      <input
        type="range"
        className="h-1.5 flex-1 appearance-none rounded-full bg-white/10 accent-accent-1"
        min={0}
        max={1}
        step={0.05}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      <span className="w-12 text-right font-mono text-xs text-muted">
        {Math.round(value * 100)}%
      </span>
    </div>
  )
}

export default function PresetForm({ preset, onClose }: PresetFormProps) {
  const save = useSavePreset()

  const [form, setForm] = useState<PresetInput>({
    name: preset?.name ?? '',
    plateforme: preset?.plateforme ?? 'ig',
    session_type: preset?.session_type ?? 'browse',
    description: preset?.description ?? null,
    is_default: preset?.is_default ?? false,
    config: preset?.config ?? { ...DEFAULT_CONFIG },
  })

  const probs = (form.config.probabilities ?? {}) as Record<string, number>
  const pauses = (form.config.pauses ?? { min: 2, max: 8 }) as { min: number; max: number }
  const durations = (form.config.durations ?? { min: 15, max: 45 }) as { min: number; max: number }

  const setProb = (key: string, val: number) => {
    setForm({
      ...form,
      config: { ...form.config, probabilities: { ...probs, [key]: val } },
    })
  }

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    save.mutate({ id: preset?.id, data: form }, { onSuccess: onClose })
  }

  return (
    <Modal
      title={preset ? `Modifier « ${preset.name} »` : 'Nouveau preset'}
      onClose={onClose}
      width={640}
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Annuler
          </button>
          <button
            type="submit"
            form="preset-form"
            className="btn btn-primary"
            disabled={save.isPending || !form.name.trim()}
          >
            <FloppyDisk size={16} /> Enregistrer
          </button>
        </>
      }
    >
      <form id="preset-form" onSubmit={submit} className="space-y-5">
        {/* Basic info */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Nom</label>
            <input
              className="field"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              autoFocus
            />
          </div>
          <div>
            <label className="label">Description</label>
            <input
              className="field"
              value={form.description ?? ''}
              placeholder="Optionnel"
              onChange={(e) => setForm({ ...form, description: e.target.value || null })}
            />
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="label">Plateforme</label>
            <select
              className="field"
              value={form.plateforme}
              onChange={(e) => setForm({ ...form, plateforme: e.target.value as Platform })}
            >
              {PLATFORMS.map((p) => (
                <option key={p} value={p}>
                  {PLATFORM_META[p].label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">Type de session</label>
            <select
              className="field"
              value={form.session_type}
              onChange={(e) => setForm({ ...form, session_type: e.target.value as SessionType })}
            >
              {SESSION_TYPES.map((t) => (
                <option key={t} value={t}>
                  {SESSION_TYPE_LABELS[t]}
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-end pb-1">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.is_default}
                onChange={(e) => setForm({ ...form, is_default: e.target.checked })}
                className="accent-accent-1"
              />
              Par defaut
            </label>
          </div>
        </div>

        {/* Probabilities */}
        <div>
          <h3 className="label mb-3">Probabilites d'action</h3>
          <div className="space-y-3 rounded-xl bg-white/[0.02] p-4">
            {Object.entries(probs).map(([key, val]) => (
              <ProbabilitySlider
                key={key}
                label={key.replace(/_/g, ' ')}
                value={val}
                onChange={(v) => setProb(key, v)}
              />
            ))}
          </div>
        </div>

        {/* Pauses & durations */}
        <div className="grid grid-cols-2 gap-5">
          <div>
            <h3 className="label mb-3">Pauses entre actions (sec)</h3>
            <div className="grid grid-cols-2 gap-3">
              <NumberField
                label="Min"
                value={pauses.min}
                onChange={(v) =>
                  setForm({
                    ...form,
                    config: { ...form.config, pauses: { ...pauses, min: v } },
                  })
                }
              />
              <NumberField
                label="Max"
                value={pauses.max}
                onChange={(v) =>
                  setForm({
                    ...form,
                    config: { ...form.config, pauses: { ...pauses, max: v } },
                  })
                }
              />
            </div>
          </div>
          <div>
            <h3 className="label mb-3">Durees de session (min)</h3>
            <div className="grid grid-cols-2 gap-3">
              <NumberField
                label="Min"
                value={durations.min}
                onChange={(v) =>
                  setForm({
                    ...form,
                    config: { ...form.config, durations: { ...durations, min: v } },
                  })
                }
              />
              <NumberField
                label="Max"
                value={durations.max}
                onChange={(v) =>
                  setForm({
                    ...form,
                    config: { ...form.config, durations: { ...durations, max: v } },
                  })
                }
              />
            </div>
          </div>
        </div>
      </form>
    </Modal>
  )
}
