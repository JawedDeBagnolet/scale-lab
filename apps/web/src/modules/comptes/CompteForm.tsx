import { useState, type FormEvent } from 'react'
import Modal from '../../components/Modal'
import { PLATFORM_META } from '../../components/PlatformBadge'
import { useIphones, useSaveCompte } from '../../hooks/useApi'
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
  const [password, setPassword] = useState('')
  const [twoFa, setTwoFa] = useState('')

  const save = useSaveCompte()
  const { data: iphones } = useIphones()
  const cleanHandle = handle.trim().replace(/^@/, '')

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const payload: Record<string, unknown> = {
      handle: cleanHandle,
      persona_id: personaId || null,
      plateforme,
      workflow,
      status,
      device_id: deviceId || null,
    }

    // Include credentials if password is provided
    if (password.trim()) {
      payload.creds_encrypted = {
        password: password.trim(),
        ...(twoFa.trim() ? { two_fa: twoFa.trim() } : {}),
      }
    }

    save.mutate(
      { id: compte?.id, data: payload },
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

          {/* iPhone assignment */}
          <div className="col-span-2">
            <label className="label" htmlFor="cf-device">iPhone</label>
            <select id="cf-device" className="field" value={deviceId} onChange={(e) => setDeviceId(e.target.value)}>
              <option value="">Aucun</option>
              {iphones?.map((ip) => (
                <option key={ip.id} value={ip.id}>
                  {ip.name} — {ip.status === 'online' ? '🟢' : '🔴'} {ip.model}
                </option>
              ))}
            </select>
          </div>

          {/* Credentials */}
          <div className="col-span-2" style={{ borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: 16, marginTop: 4 }}>
            <p className="label" style={{ marginBottom: 8, opacity: 0.6 }}>
              Identifiants {PLATFORM_META[plateforme].label} {compte ? '(laisser vide pour ne pas modifier)' : ''}
            </p>
          </div>
          <div>
            <label className="label" htmlFor="cf-pwd">Mot de passe</label>
            <input id="cf-pwd" className="field" type="password" autoComplete="off"
              placeholder={compte ? '••••••••' : 'Mot de passe'}
              value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
          <div>
            <label className="label" htmlFor="cf-2fa">2FA (clé TOTP ou code)</label>
            <input id="cf-2fa" className="field" autoComplete="off"
              placeholder="Optionnel"
              value={twoFa} onChange={(e) => setTwoFa(e.target.value)} />
          </div>
        </div>
      </Modal>
    </form>
  )
}
