import { useState } from 'react'
import {
  ChatCircle,
  CheckCircle,
  FloppyDisk,
  GearSix,
  Link as LinkIcon,
  XCircle,
} from '@phosphor-icons/react'
import { ErrorState, Loading } from '../../components/StateBlock'
import {
  useSettings,
  useUpdateIntegration,
  useUpdateNotifications,
  useUpdateWorkspace,
} from '../../hooks/useApi'
import type { IntegrationUpdate, NotificationsConfig, WorkspaceUpdate } from '../../types/settings'

// --- Workspace card ----------------------------------------------------------

function WorkspaceCard() {
  const { data } = useSettings()
  const update = useUpdateWorkspace()
  const [form, setForm] = useState<WorkspaceUpdate | null>(null)

  if (!data) return null
  const editing = form !== null
  const current = form ?? { name: data.name, currency: data.currency, timezone: data.timezone }

  const save = () => {
    if (!form) return
    update.mutate(form, { onSuccess: () => setForm(null) })
  }

  return (
    <section className="card p-6">
      <div className="mb-5 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-base font-bold">
          <GearSix size={20} className="text-accent-1" /> Workspace
        </h2>
        {!editing && (
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() =>
              setForm({ name: data.name, currency: data.currency, timezone: data.timezone })
            }
          >
            Modifier
          </button>
        )}
      </div>

      <div className="grid grid-cols-3 gap-5">
        <div>
          <label className="label">Nom</label>
          {editing ? (
            <input
              className="field"
              value={current.name ?? ''}
              onChange={(e) => setForm({ ...form!, name: e.target.value })}
            />
          ) : (
            <div className="text-sm">{data.name}</div>
          )}
        </div>
        <div>
          <label className="label">Devise</label>
          {editing ? (
            <select
              className="field"
              value={current.currency ?? 'EUR'}
              onChange={(e) => setForm({ ...form!, currency: e.target.value })}
            >
              <option value="EUR">EUR</option>
              <option value="USD">USD</option>
              <option value="GBP">GBP</option>
            </select>
          ) : (
            <div className="text-sm">{data.currency}</div>
          )}
        </div>
        <div>
          <label className="label">Fuseau horaire</label>
          {editing ? (
            <input
              className="field"
              value={current.timezone ?? ''}
              onChange={(e) => setForm({ ...form!, timezone: e.target.value })}
            />
          ) : (
            <div className="text-sm">{data.timezone}</div>
          )}
        </div>
      </div>

      {editing && (
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" className="btn btn-ghost" onClick={() => setForm(null)}>
            Annuler
          </button>
          <button
            type="button"
            className="btn btn-primary"
            disabled={update.isPending}
            onClick={save}
          >
            <FloppyDisk size={16} /> Enregistrer
          </button>
        </div>
      )}
    </section>
  )
}

// --- Integration card --------------------------------------------------------

const INTEGRATION_META: Record<string, { label: string; description: string; fields: string[] }> = {
  oc: {
    label: 'OnlyChat',
    description: 'Synchronisation des creatrices, fans, transactions et scripts.',
    fields: ['api_key'],
  },
  gms: {
    label: 'GetMySocial',
    description: 'Liens trackes, landings et analytics.',
    fields: ['api_key'],
  },
  tg: {
    label: 'Telegram',
    description: 'Alertes et notifications en temps reel.',
    fields: ['bot_token', 'chat_id'],
  },
}

const FIELD_LABELS: Record<string, string> = {
  api_key: 'Cle API',
  bot_token: 'Bot Token',
  chat_id: 'Chat ID',
}

function IntegrationCard({ provider }: { provider: string }) {
  const { data } = useSettings()
  const update = useUpdateIntegration()
  const [form, setForm] = useState<IntegrationUpdate | null>(null)

  if (!data) return null
  const meta = INTEGRATION_META[provider]
  if (!meta) return null

  const status = data[provider as keyof typeof data] as {
    connected: boolean
    last_sync: string | null
    key_tail: string | null
  }
  const editing = form !== null

  const save = () => {
    if (!form) return
    update.mutate({ provider, data: form }, { onSuccess: () => setForm(null) })
  }

  return (
    <div className="card p-5">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="flex items-center gap-2 text-sm font-bold">
            {provider === 'tg' ? (
              <ChatCircle size={18} className="text-accent-2" />
            ) : (
              <LinkIcon size={18} className="text-accent-2" />
            )}
            {meta.label}
          </h3>
          <p className="mt-0.5 text-xs text-muted">{meta.description}</p>
        </div>
        <span
          className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ${
            status.connected ? 'bg-success/15 text-success' : 'bg-white/5 text-dim'
          }`}
        >
          {status.connected ? (
            <>
              <CheckCircle size={14} weight="fill" /> Connecte
            </>
          ) : (
            <>
              <XCircle size={14} weight="fill" /> Non connecte
            </>
          )}
        </span>
      </div>

      {!editing && status.key_tail && (
        <div className="mb-3 text-xs text-muted">
          Cle configuree : ***{status.key_tail}
          {status.last_sync && (
            <span className="ml-3">
              Derniere sync : {new Date(status.last_sync).toLocaleString('fr-FR')}
            </span>
          )}
        </div>
      )}

      {editing ? (
        <div className="space-y-3">
          {meta.fields.map((field) => (
            <div key={field}>
              <label className="label">{FIELD_LABELS[field] ?? field}</label>
              <input
                className="field"
                type="password"
                placeholder={status.key_tail ? `***${status.key_tail}` : 'Entrer la valeur'}
                value={(form as Record<string, string>)[field] ?? ''}
                onChange={(e) => setForm({ ...form!, [field]: e.target.value })}
              />
            </div>
          ))}
          <div className="flex justify-end gap-2 pt-1">
            <button type="button" className="btn btn-ghost" onClick={() => setForm(null)}>
              Annuler
            </button>
            <button
              type="button"
              className="btn btn-primary"
              disabled={update.isPending}
              onClick={save}
            >
              <FloppyDisk size={16} /> Enregistrer
            </button>
          </div>
        </div>
      ) : (
        <button type="button" className="btn btn-ghost" onClick={() => setForm({})}>
          {status.connected ? 'Modifier' : 'Configurer'}
        </button>
      )}
    </div>
  )
}

// --- Notifications card ------------------------------------------------------

function NotificationsCard() {
  const { data } = useSettings()
  const update = useUpdateNotifications()

  if (!data) return null

  const notif: NotificationsConfig = (data.notifications as NotificationsConfig) ?? {}

  const toggle = (key: keyof NotificationsConfig) => {
    update.mutate({ ...notif, [key]: !notif[key] })
  }

  const items: { key: keyof NotificationsConfig; label: string; desc: string }[] = [
    { key: 'domain_full', label: 'Domaine plein', desc: 'Alerte quand un domaine est sature' },
    {
      key: 'oc_balance_low',
      label: 'Solde OC bas',
      desc: 'Alerte quand le solde OnlyChat est faible',
    },
    {
      key: 'link_unavailable',
      label: 'Lien indisponible',
      desc: 'Alerte quand un lien tracke tombe',
    },
  ]

  return (
    <section className="card p-6">
      <h2 className="mb-5 text-base font-bold">Notifications Telegram</h2>
      <div className="space-y-4">
        {items.map(({ key, label, desc }) => (
          <label key={key} className="flex items-center justify-between">
            <div>
              <div className="text-sm font-medium">{label}</div>
              <div className="text-xs text-muted">{desc}</div>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={!!notif[key]}
              onClick={() => toggle(key)}
              disabled={update.isPending}
              className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors ${
                notif[key] ? 'bg-accent-1' : 'bg-white/10'
              }`}
            >
              <span
                className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow transition-transform ${
                  notif[key] ? 'translate-x-5' : 'translate-x-0'
                }`}
              />
            </button>
          </label>
        ))}
      </div>
    </section>
  )
}

// --- Main page ---------------------------------------------------------------

export default function ParametresPage() {
  const settings = useSettings()

  if (settings.isLoading) return <Loading />
  if (settings.isError)
    return <ErrorState error={settings.error} onRetry={() => settings.refetch()} />

  return (
    <div className="space-y-6">
      <WorkspaceCard />

      <section>
        <h2 className="mb-4 text-base font-bold">Integrations</h2>
        <div className="grid grid-cols-3 gap-5">
          {Object.keys(INTEGRATION_META).map((provider) => (
            <IntegrationCard key={provider} provider={provider} />
          ))}
        </div>
      </section>

      <NotificationsCard />
    </div>
  )
}
