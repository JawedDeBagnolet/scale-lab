import { useState, type FormEvent } from 'react'
import Modal from '../../components/Modal'
import { PLATFORM_META } from '../../components/PlatformBadge'
import { useSaveCompte } from '../../hooks/useApi'
import {
  PLATFORMS, STATUSES, WORKFLOWS,
  type Compte, type CompteStatus, type CompteWorkflow, type Platform,
} from '../../types/compte'
import type { Persona } from '../../types/persona'
import { STATUS_LABELS } from './labels'

interface Props {
  compte?: Compte
  personas: Persona[]
  defaultPersonaId?: string
  onClose: () => void
}

export default function CompteForm({ compte, personas, defaultPersonaId, onClose }: Props) {
  const [handle, setHandle] = useState(compte?.handle ?? '')
  const [personaId, setPersonaId] = useState(compte?.persona_id ?? defaultPersonaId ?? '')
  const [plateforme, setPlateforme] = useState<Platform>(compte?.plateforme ?? 'ig')
  const [workflow, setWorkflow] = useState<CompteWorkflow>(compte?.workflow ?? 'Onboarding')
  const [status, setStatus] = useState<CompteStatus>(compte?.status ?? 'ok')
  const [deviceId, setDeviceId] = useState(compte?.device_id ?? '')

  const save = useSaveCompte()
  const cleanHandle = handle.trim().replace(/^@/, '')

  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate(
      {
        id: compte?.id,
        data: {
          handle: cleanHandle,
          persona_id: personaId || null,
          plateforme,
          workflow,
          status,
          device_id: deviceId.trim() || null,
        },
      },
      { onSuccess: onClose },
    )
  }

  return (
    <form onSubmit={submit}>
      <Modal
        title={compte ? `Modifier @${compte.handle}` : 'Nouveau compte'}
        onClose={onClose}
        width={560}
        footer={
          <>
            <button type="button" className="btn btn-ghost" onClick={onClose}>
              Annuler
            </button>
            <button type="submit" className="btn btn-primary" disabled={save.isPending || !cleanHandle}>
              {save.isPending ? 'Enregistrement...' : 'Enregistrer'}
            </button>
          </>
        }
      >
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label" htmlFor="cf-handle">Handle *</label>
            <input id="cf-handle" className="field" required maxLength={100} autoFocus placeholder="@handle"
              value={handle} onChange={(e) => setHandle(e.target.value)} />
          </div>
          <div>
            <label className="label" htmlFor="cf-plat">Plateforme *</label>
            <select id="cf-plat" className="field" value={plateforme} onChange={(e) => setPlateforme(e.target.value as Platform)}>
              {PLATFORMS.map((p) => <option key={p} value={p}>{PLATFORM_META[p].label}</option>)}
            </select>
          </div>
          <div className="col-span-2">
            <label className="label" htmlFor="cf-persona">Persona</label>
            <select id="cf-persona" className="field" value={personaId} onChange={(e) => setPersonaId(e.target.value)}>
              <option value="">Aucune</option>
              {personas.map((p) => (
                <option key={p.id} value={p.id}>{p.first_name} {p.last_name ?? ''}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="cf-workflow">Workflow</label>
            <select id="cf-workflow" className="field" value={workflow} onChange={(e) => setWorkflow(e.target.value as CompteWorkflow)}>
              {WORKFLOWS.map((w) => <option key={w} value={w}>{w}</option>)}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="cf-status">Statut</label>
            <select id="cf-status" className="field" value={status} onChange={(e) => setStatus(e.target.value as CompteStatus)}>
              {STATUSES.map((st) => <option key={st} value={st}>{STATUS_LABELS[st]}</option>)}
            </select>
          </div>
          <div className="col-span-2">
            <label className="label" htmlFor="cf-device">Device (iPhone)</label>
            <input id="cf-device" className="field" maxLength={100}
              value={deviceId} onChange={(e) => setDeviceId(e.target.value)} />
          </div>
        </div>
      </Modal>
    </form>
  )
}
