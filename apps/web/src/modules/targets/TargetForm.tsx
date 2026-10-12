import { useState } from 'react'
import { FloppyDisk } from '@phosphor-icons/react'
import Modal from '../../components/Modal'
import { PLATFORM_META } from '../../components/PlatformBadge'
import { useMarches, useNiches, useSaveTarget } from '../../hooks/useApi'
import { PLATFORMS, type Platform } from '../../types/compte'
import { TARGET_STATUSES, TARGET_SOURCES, type Target, type TargetInput } from '../../types/target'

interface TargetFormProps {
  target?: Target
  onClose: () => void
}

const STATUS_LABELS: Record<string, string> = {
  ok: 'OK',
  prive: 'Prive',
  renomme: 'Renomme',
  banni: 'Banni',
}

const SOURCE_LABELS: Record<string, string> = {
  manual: 'Manuel',
  veille: 'Veille',
  import: 'Import',
}

export default function TargetForm({ target, onClose }: TargetFormProps) {
  const save = useSaveTarget()
  const niches = useNiches()
  const marches = useMarches()

  const [form, setForm] = useState<TargetInput>({
    handle: target?.handle ?? '',
    plateforme: target?.plateforme ?? 'ig',
    market: target?.market ?? null,
    niche_id: target?.niche_id ?? null,
    status: target?.status ?? 'ok',
    source: target?.source ?? 'manual',
  })

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    save.mutate(
      { id: target?.id, data: form },
      { onSuccess: onClose },
    )
  }

  return (
    <Modal
      title={target ? `Modifier @${target.handle}` : 'Nouvelle target'}
      onClose={onClose}
      width={540}
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Annuler
          </button>
          <button
            type="submit"
            form="target-form"
            className="btn btn-primary"
            disabled={save.isPending || !form.handle.trim()}
          >
            <FloppyDisk size={16} /> Enregistrer
          </button>
        </>
      }
    >
      <form id="target-form" onSubmit={submit} className="space-y-4">
        <div>
          <label className="label">Handle</label>
          <input
            className="field"
            placeholder="@username"
            value={form.handle}
            onChange={(e) => setForm({ ...form, handle: e.target.value.replace(/^@/, '') })}
            autoFocus
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
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
            <label className="label">Marche</label>
            <select
              className="field"
              value={form.market ?? ''}
              onChange={(e) => setForm({ ...form, market: e.target.value || null })}
            >
              <option value="">Aucun</option>
              {marches.data?.map((m) => (
                <option key={m.code} value={m.code}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="label">Niche</label>
            <select
              className="field"
              value={form.niche_id ?? ''}
              onChange={(e) =>
                setForm({ ...form, niche_id: e.target.value ? Number(e.target.value) : null })
              }
            >
              <option value="">Aucune</option>
              {niches.data?.map((n) => (
                <option key={n.id} value={n.id}>
                  {n.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">Statut</label>
            <select
              className="field"
              value={form.status}
              onChange={(e) => setForm({ ...form, status: e.target.value as typeof form.status })}
            >
              {TARGET_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {STATUS_LABELS[s]}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">Source</label>
            <select
              className="field"
              value={form.source}
              onChange={(e) => setForm({ ...form, source: e.target.value as typeof form.source })}
            >
              {TARGET_SOURCES.map((s) => (
                <option key={s} value={s}>
                  {SOURCE_LABELS[s]}
                </option>
              ))}
            </select>
          </div>
        </div>
      </form>
    </Modal>
  )
}
