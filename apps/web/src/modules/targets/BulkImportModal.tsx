import { useState } from 'react'
import { UploadSimple } from '@phosphor-icons/react'
import Modal from '../../components/Modal'
import { PLATFORM_META } from '../../components/PlatformBadge'
import { useBulkCreateTargets } from '../../hooks/useApi'
import { PLATFORMS, type Platform } from '../../types/compte'
import type { TargetInput } from '../../types/target'

interface BulkImportModalProps {
  onClose: () => void
}

export default function BulkImportModal({ onClose }: BulkImportModalProps) {
  const bulk = useBulkCreateTargets()
  const [raw, setRaw] = useState('')
  const [plateforme, setPlateforme] = useState<Platform>('ig')

  const lines = raw
    .split('\n')
    .map((l) => l.trim().replace(/^@/, ''))
    .filter(Boolean)

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    if (lines.length === 0) return
    const targets: TargetInput[] = lines.map((handle) => ({
      handle,
      plateforme,
      market: null,
      niche_id: null,
      status: 'ok',
      source: 'import',
    }))
    bulk.mutate(targets, { onSuccess: onClose })
  }

  return (
    <Modal
      title="Import en masse"
      onClose={onClose}
      width={520}
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Annuler
          </button>
          <button
            type="submit"
            form="bulk-form"
            className="btn btn-primary"
            disabled={bulk.isPending || lines.length === 0}
          >
            <UploadSimple size={16} /> Importer {lines.length > 0 ? `(${lines.length})` : ''}
          </button>
        </>
      }
    >
      <form id="bulk-form" onSubmit={submit} className="space-y-4">
        <div>
          <label className="label">Plateforme</label>
          <select
            className="field"
            value={plateforme}
            onChange={(e) => setPlateforme(e.target.value as Platform)}
          >
            {PLATFORMS.map((p) => (
              <option key={p} value={p}>
                {PLATFORM_META[p].label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label">Handles (un par ligne)</label>
          <textarea
            className="field min-h-[180px] font-mono text-xs"
            placeholder={'username1\nusername2\nusername3'}
            value={raw}
            onChange={(e) => setRaw(e.target.value)}
            autoFocus
          />
          {lines.length > 0 && (
            <div className="mt-1 text-xs text-muted">
              {lines.length} handle{lines.length > 1 ? 's' : ''} detecte{lines.length > 1 ? 's' : ''}
            </div>
          )}
        </div>
      </form>
    </Modal>
  )
}
