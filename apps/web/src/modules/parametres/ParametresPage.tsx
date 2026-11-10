import { useState } from 'react'
import {
  ChatCircle,
  CheckCircle,
  FloppyDisk,
  GearSix,
  Globe,
  Link as LinkIcon,
  MagnifyingGlass,
  Plus,
  Trash,
  XCircle,
} from '@phosphor-icons/react'
import { ErrorState, Loading } from '../../components/StateBlock'
import {
  useCreateScraperAccount,
  useDeleteScraperAccount,
  useScraperAccounts,
  useSettings,
  useUpdateIntegration,
  useUpdateNotifications,
  useUpdateWorkspace,
  useVerifyScraperAccount,
} from '../../hooks/useApi'
import type { IntegrationUpdate, NotificationsConfig, ScraperAccountCreate, WorkspaceUpdate } from '../../types/settings'

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
  scrapigo: {
    label: 'Scrapigo',
    description: 'Proxies residentiels pour le scraping API privee IG, Threads et X.',
    fields: ['api_key'],
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

// --- Scraper Accounts card ---------------------------------------------------

const PLATFORM_LABELS: Record<string, string> = { ig: 'Instagram', threads: 'Threads', x: 'X' }
const STATUS_COLORS: Record<string, string> = {
  active: 'bg-success/15 text-success',
  pending: 'bg-white/5 text-dim',
  expired: 'bg-warning/15 text-warning',
  banned: 'bg-error/15 text-error',
  rate_limited: 'bg-warning/15 text-warning',
}

function ScraperAccountsCard() {
  const { data: accounts, isLoading } = useScraperAccounts()
  const create = useCreateScraperAccount()
  const remove = useDeleteScraperAccount()
  const verify = useVerifyScraperAccount()
  const [adding, setAdding] = useState(false)
  const [form, setForm] = useState<ScraperAccountCreate>({
    platform: 'ig',
    username: '',
    password: '',
    proxy_country: 'FR',
  })

  const handleCreate = () => {
    if (!form.username.trim()) return
    create.mutate(form, {
      onSuccess: () => {
        setAdding(false)
        setForm({ platform: 'ig', username: '', password: '', proxy_country: 'FR' })
      },
    })
  }

  const formatBytes = (b: number) => {
    if (b < 1024) return `${b} B`
    if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`
    if (b < 1024 * 1024 * 1024) return `${(b / (1024 * 1024)).toFixed(1)} MB`
    return `${(b / (1024 * 1024 * 1024)).toFixed(2)} GB`
  }

  return (
    <section className="card p-6">
      <div className="mb-5 flex items-center justify-between">
        <div>
          <h2 className="flex items-center gap-2 text-base font-bold">
            <MagnifyingGlass size={20} className="text-accent-1" /> Comptes Scraper
          </h2>
          <p className="mt-0.5 text-xs text-muted">
            Comptes dedies au scraping API privee (veille, recherche, statistiques)
          </p>
        </div>
        <button type="button" className="btn btn-primary" onClick={() => setAdding(true)}>
          <Plus size={16} /> Ajouter
        </button>
      </div>

      {adding && (
        <div className="mb-5 rounded-xl border border-white/[.07] bg-white/[.022] p-4">
          <div className="grid grid-cols-4 gap-3">
            <div>
              <label className="label">Plateforme</label>
              <select
                className="field"
                value={form.platform}
                onChange={(e) => setForm({ ...form, platform: e.target.value })}
              >
                <option value="ig">Instagram</option>
                <option value="threads">Threads</option>
                <option value="x">X</option>
              </select>
            </div>
            <div>
              <label className="label">Username</label>
              <input
                className="field"
                placeholder="@username"
                value={form.username}
                onChange={(e) => setForm({ ...form, username: e.target.value })}
              />
            </div>
            <div>
              <label className="label">Mot de passe</label>
              <input
                className="field"
                type="password"
                placeholder="••••••"
                value={form.password ?? ''}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
              />
            </div>
            <div>
              <label className="label">Pays proxy</label>
              <select
                className="field"
                value={form.proxy_country}
                onChange={(e) => setForm({ ...form, proxy_country: e.target.value })}
              >
                <option value="FR">France</option>
                <option value="US">USA</option>
                <option value="GB">UK</option>
                <option value="DE">Allemagne</option>
              </select>
            </div>
          </div>
          <div className="mt-3 flex justify-end gap-2">
            <button type="button" className="btn btn-ghost" onClick={() => setAdding(false)}>
              Annuler
            </button>
            <button
              type="button"
              className="btn btn-primary"
              disabled={create.isPending || !form.username.trim()}
              onClick={handleCreate}
            >
              <FloppyDisk size={16} /> Creer
            </button>
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="text-xs text-muted">Chargement...</div>
      ) : !accounts?.length ? (
        <div className="text-center text-xs text-dim py-8">
          Aucun compte scraper configure
        </div>
      ) : (
        <div className="space-y-2">
          {accounts.map((a) => (
            <div
              key={a.id}
              className="flex items-center gap-3 rounded-xl border border-white/[.06] bg-white/[.02] px-4 py-3"
            >
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent-1/10 text-xs font-bold text-accent-1">
                {a.platform.toUpperCase().slice(0, 2)}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold">@{a.username}</span>
                  <span className="text-xs text-muted">{PLATFORM_LABELS[a.platform] ?? a.platform}</span>
                </div>
                {a.last_error && (
                  <div className="mt-0.5 truncate text-xs text-error">{a.last_error}</div>
                )}
              </div>
              <div className="text-right">
                <div className="text-xs tabular-nums text-muted">{formatBytes(a.bytes_used)}</div>
                <div className="text-[11px] text-dim">{a.requests_count.toLocaleString('fr-FR')} req</div>
              </div>
              <div className="flex items-center gap-1">
                <Globe size={13} className="text-dim" />
                <span className="text-xs text-muted">{a.proxy_country}</span>
              </div>
              <span
                className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold ${STATUS_COLORS[a.status] ?? 'bg-white/5 text-dim'}`}
              >
                {a.has_session ? (
                  <><CheckCircle size={12} weight="fill" className="mr-1" />{a.status}</>
                ) : (
                  <><XCircle size={12} weight="fill" className="mr-1" />sans session</>
                )}
              </span>
              <button
                type="button"
                className="btn btn-ghost p-1.5"
                title="Verifier la session"
                onClick={() => verify.mutate(a.id)}
              >
                <CheckCircle size={16} />
              </button>
              <button
                type="button"
                className="btn btn-ghost p-1.5 hover:text-error"
                title="Supprimer"
                onClick={() => {
                  if (confirm(`Supprimer @${a.username} ?`)) remove.mutate(a.id)
                }}
              >
                <Trash size={16} />
              </button>
            </div>
          ))}
        </div>
      )}
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

      <ScraperAccountsCard />

      <NotificationsCard />
    </div>
  )
}
