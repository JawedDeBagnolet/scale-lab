import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { FloppyDisk, Globe, Link, PencilSimple, Plus, Trash } from '@phosphor-icons/react'
import ConfirmDialog from '../../components/ConfirmDialog'
import Modal from '../../components/Modal'
import PlatformBadge, { PLATFORM_META } from '../../components/PlatformBadge'
import { Empty, ErrorState, Loading } from '../../components/StateBlock'
import {
  useDeleteDomain,
  useDeleteLink,
  useDomains,
  useLinks,
  useSaveDomain,
  useSaveLink,
} from '../../hooks/useApi'
import { PLATFORMS, type Platform } from '../../types/compte'
import {
  LINK_TYPES,
  type Domain,
  type DomainInput,
  type LinkInput,
  type LinkType,
  type TrackedLink,
} from '../../types/lien'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const isPlatform = (v: string | null): v is Platform => PLATFORMS.includes(v as Platform)

const LINK_TYPE_LABELS: Record<LinkType, string> = {
  direct: 'Direct',
  landing: 'Landing',
}

const truncate = (s: string, max = 50) => (s.length > max ? `${s.slice(0, max)}...` : s)

// ---------------------------------------------------------------------------
// Tab constants
// ---------------------------------------------------------------------------

type Tab = 'liens' | 'domaines'
const TABS: { key: Tab; label: string }[] = [
  { key: 'liens', label: 'Liens' },
  { key: 'domaines', label: 'Domaines' },
]

// ---------------------------------------------------------------------------
// Link Form Modal
// ---------------------------------------------------------------------------

function LinkForm({
  link,
  domains,
  onClose,
}: {
  link?: TrackedLink
  domains: Domain[]
  onClose: () => void
}) {
  const save = useSaveLink()

  const [form, setForm] = useState<LinkInput>({
    domain_id: link?.domain_id ?? null,
    slug: link?.slug ?? '',
    link_type: link?.link_type ?? 'direct',
    destination: link?.destination ?? '',
    plateforme: link?.plateforme ?? 'ig',
    persona_id: link?.persona_id ?? null,
    compte_id: link?.compte_id ?? null,
    active: link?.active ?? true,
    group_name: link?.group_name ?? null,
  })

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    save.mutate({ id: link?.id, data: form }, { onSuccess: onClose })
  }

  return (
    <Modal
      title={link ? `Modifier /${link.slug}` : 'Nouveau lien'}
      onClose={onClose}
      width={540}
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Annuler
          </button>
          <button
            type="submit"
            form="link-form"
            className="btn btn-primary"
            disabled={save.isPending || !form.slug.trim() || !form.destination.trim()}
          >
            <FloppyDisk size={16} /> Enregistrer
          </button>
        </>
      }
    >
      <form id="link-form" onSubmit={submit} className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Slug</label>
            <input
              className="field"
              placeholder="mon-lien"
              value={form.slug}
              onChange={(e) => setForm({ ...form, slug: e.target.value })}
              autoFocus
            />
          </div>
          <div>
            <label className="label">Type</label>
            <select
              className="field"
              value={form.link_type}
              onChange={(e) => setForm({ ...form, link_type: e.target.value as LinkType })}
            >
              {LINK_TYPES.map((t) => (
                <option key={t} value={t}>
                  {LINK_TYPE_LABELS[t]}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label className="label">Destination</label>
          <input
            className="field"
            placeholder="https://..."
            value={form.destination}
            onChange={(e) => setForm({ ...form, destination: e.target.value })}
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
            <label className="label">Domaine</label>
            <select
              className="field"
              value={form.domain_id ?? ''}
              onChange={(e) => setForm({ ...form, domain_id: e.target.value || null })}
            >
              <option value="">Aucun</option>
              {domains.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.host}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Groupe</label>
            <input
              className="field"
              placeholder="Nom du groupe (optionnel)"
              value={form.group_name ?? ''}
              onChange={(e) => setForm({ ...form, group_name: e.target.value || null })}
            />
          </div>
          <div className="flex items-end pb-1">
            <label className="flex items-center gap-2 text-[13px]">
              <input
                type="checkbox"
                checked={form.active}
                onChange={(e) => setForm({ ...form, active: e.target.checked })}
              />
              Actif
            </label>
          </div>
        </div>
      </form>
    </Modal>
  )
}

// ---------------------------------------------------------------------------
// Domain Form Modal
// ---------------------------------------------------------------------------

function DomainForm({
  domain,
  onClose,
}: {
  domain?: Domain
  onClose: () => void
}) {
  const save = useSaveDomain()

  const [form, setForm] = useState<DomainInput>({
    host: domain?.host ?? '',
    max_active_links: domain?.max_active_links ?? 500,
    alert_threshold: domain?.alert_threshold ?? 450,
  })

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    save.mutate({ id: domain?.id, data: form }, { onSuccess: onClose })
  }

  return (
    <Modal
      title={domain ? `Modifier ${domain.host}` : 'Nouveau domaine'}
      onClose={onClose}
      width={480}
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Annuler
          </button>
          <button
            type="submit"
            form="domain-form"
            className="btn btn-primary"
            disabled={save.isPending || !form.host.trim()}
          >
            <FloppyDisk size={16} /> Enregistrer
          </button>
        </>
      }
    >
      <form id="domain-form" onSubmit={submit} className="space-y-4">
        <div>
          <label className="label">Host</label>
          <input
            className="field"
            placeholder="go.example.com"
            value={form.host}
            onChange={(e) => setForm({ ...form, host: e.target.value })}
            autoFocus
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Liens actifs max</label>
            <input
              type="number"
              className="field"
              value={form.max_active_links}
              onChange={(e) => setForm({ ...form, max_active_links: Number(e.target.value) })}
            />
          </div>
          <div>
            <label className="label">Seuil d'alerte</label>
            <input
              type="number"
              className="field"
              value={form.alert_threshold}
              onChange={(e) => setForm({ ...form, alert_threshold: Number(e.target.value) })}
            />
          </div>
        </div>
      </form>
    </Modal>
  )
}

// ---------------------------------------------------------------------------
// Links Tab
// ---------------------------------------------------------------------------

function LinksTab({ domains }: { domains: Domain[] }) {
  const [params, setParams] = useSearchParams()
  const plat = params.get('plat')
  const domainId = params.get('domain') ?? undefined
  const plateforme = isPlatform(plat) ? plat : undefined

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }

  const links = useLinks({ plateforme, domain_id: domainId })
  const del = useDeleteLink()
  const toggleActive = useSaveLink()

  const [editing, setEditing] = useState<TrackedLink | null | undefined>(undefined)
  const [deleting, setDeleting] = useState<TrackedLink | null>(null)

  const domainMap = new Map(domains.map((d) => [d.id, d.host]))
  const filtered = Boolean(plateforme || domainId)

  return (
    <>
      <div className="mb-6 flex items-center gap-3">
        <select
          className="field w-48"
          aria-label="Filtrer par domaine"
          value={domainId ?? ''}
          onChange={(e) => setFilter('domain', e.target.value)}
        >
          <option value="">Tous les domaines</option>
          {domains.map((d) => (
            <option key={d.id} value={d.id}>
              {d.host}
            </option>
          ))}
        </select>
        <select
          className="field w-48"
          aria-label="Filtrer par plateforme"
          value={plateforme ?? ''}
          onChange={(e) => setFilter('plat', e.target.value)}
        >
          <option value="">Toutes les plateformes</option>
          {PLATFORMS.map((p) => (
            <option key={p} value={p}>
              {PLATFORM_META[p].label}
            </option>
          ))}
        </select>
        <span className="text-[13px] text-muted">
          {links.data ? `${links.data.length} lien${links.data.length > 1 ? 's' : ''}` : ''}
        </span>
        <div className="ml-auto">
          <button type="button" className="btn btn-primary" onClick={() => setEditing(null)}>
            <Plus size={16} weight="bold" /> Nouveau lien
          </button>
        </div>
      </div>

      {links.isLoading && <Loading />}
      {links.isError && <ErrorState error={links.error} onRetry={() => links.refetch()} />}
      {links.data?.length === 0 && (
        <Empty>
          {filtered
            ? 'Aucun lien ne correspond aux filtres.'
            : 'Aucun lien pour le moment.'}
        </Empty>
      )}

      {links.data && links.data.length > 0 && (
        <div className="card overflow-hidden">
          <table className="w-full text-left text-[13px]">
            <thead>
              <tr className="border-b border-line text-[11px] uppercase tracking-wider text-muted">
                <th className="px-5 py-3 font-semibold">Slug</th>
                <th className="px-5 py-3 font-semibold">Destination</th>
                <th className="px-5 py-3 font-semibold">Plateforme</th>
                <th className="px-5 py-3 font-semibold">Groupe</th>
                <th className="px-5 py-3 font-semibold">Actif</th>
                <th className="w-24 px-5 py-3" />
              </tr>
            </thead>
            <tbody>
              {links.data.map((l) => (
                <tr
                  key={l.id}
                  className="border-b border-line last:border-0 hover:bg-white/[0.02]"
                >
                  <td className="px-5 py-3 font-semibold">
                    <span className="inline-flex items-center gap-1.5">
                      <Link size={14} className="text-muted" />
                      /{l.slug}
                    </span>
                    {l.domain_id && (
                      <span className="ml-2 text-[11px] text-muted">
                        {domainMap.get(l.domain_id) ?? ''}
                      </span>
                    )}
                  </td>
                  <td className="px-5 py-3 text-muted" title={l.destination}>
                    {truncate(l.destination)}
                  </td>
                  <td className="px-5 py-3">
                    <PlatformBadge platform={l.plateforme} withLabel />
                  </td>
                  <td className="px-5 py-3 text-muted">{l.group_name ?? '—'}</td>
                  <td className="px-5 py-3">
                    <button
                      type="button"
                      className="relative h-5 w-9 rounded-full transition-colors"
                      style={{ background: l.active ? '#22c55e' : '#555872' }}
                      aria-label={l.active ? 'Desactiver' : 'Activer'}
                      onClick={() =>
                        toggleActive.mutate({ id: l.id, data: { active: !l.active } })
                      }
                    >
                      <span
                        className="absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform"
                        style={{ left: l.active ? '18px' : '2px' }}
                      />
                    </button>
                  </td>
                  <td className="px-5 py-3">
                    <div className="flex justify-end gap-1">
                      <button
                        type="button"
                        className="icon-btn"
                        aria-label={`Modifier /${l.slug}`}
                        onClick={() => setEditing(l)}
                      >
                        <PencilSimple size={16} />
                      </button>
                      <button
                        type="button"
                        className="icon-btn"
                        aria-label={`Supprimer /${l.slug}`}
                        onClick={() => setDeleting(l)}
                      >
                        <Trash size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {editing !== undefined && (
        <LinkForm
          link={editing ?? undefined}
          domains={domains}
          onClose={() => setEditing(undefined)}
        />
      )}

      {deleting && (
        <ConfirmDialog
          title="Supprimer le lien"
          message={`Le lien /${deleting.slug} sera supprime definitivement.`}
          pending={del.isPending}
          onCancel={() => setDeleting(null)}
          onConfirm={() => del.mutate(deleting.id, { onSuccess: () => setDeleting(null) })}
        />
      )}
    </>
  )
}

// ---------------------------------------------------------------------------
// Domains Tab
// ---------------------------------------------------------------------------

function DomainsTab({ domains }: { domains: Domain[] }) {
  const del = useDeleteDomain()
  const [editing, setEditing] = useState<Domain | null | undefined>(undefined)
  const [deleting, setDeleting] = useState<Domain | null>(null)

  // Count active links per domain (from links query)
  const links = useLinks()
  const countByDomain = new Map<string, number>()
  if (links.data) {
    for (const l of links.data) {
      if (l.domain_id && l.active) {
        countByDomain.set(l.domain_id, (countByDomain.get(l.domain_id) ?? 0) + 1)
      }
    }
  }

  return (
    <>
      <div className="mb-6 flex items-center gap-3">
        <span className="text-[13px] text-muted">
          {domains.length} domaine{domains.length > 1 ? 's' : ''}
        </span>
        <div className="ml-auto">
          <button type="button" className="btn btn-primary" onClick={() => setEditing(null)}>
            <Plus size={16} weight="bold" /> Nouveau domaine
          </button>
        </div>
      </div>

      {domains.length === 0 && <Empty>Aucun domaine pour le moment.</Empty>}

      {domains.length > 0 && (
        <div className="card overflow-hidden">
          <table className="w-full text-left text-[13px]">
            <thead>
              <tr className="border-b border-line text-[11px] uppercase tracking-wider text-muted">
                <th className="px-5 py-3 font-semibold">Host</th>
                <th className="px-5 py-3 font-semibold">Liens actifs / Max</th>
                <th className="px-5 py-3 font-semibold">Seuil d'alerte</th>
                <th className="w-24 px-5 py-3" />
              </tr>
            </thead>
            <tbody>
              {domains.map((d) => {
                const count = countByDomain.get(d.id) ?? 0
                const nearLimit = count >= d.alert_threshold
                return (
                  <tr
                    key={d.id}
                    className="border-b border-line last:border-0 hover:bg-white/[0.02]"
                  >
                    <td className="px-5 py-3 font-semibold">
                      <span className="inline-flex items-center gap-1.5">
                        <Globe size={14} className="text-muted" />
                        {d.host}
                      </span>
                    </td>
                    <td className="px-5 py-3">
                      <span style={{ color: nearLimit ? '#f59e0b' : undefined }}>
                        {count}
                      </span>
                      <span className="text-muted"> / {d.max_active_links}</span>
                    </td>
                    <td className="px-5 py-3 text-muted">{d.alert_threshold}</td>
                    <td className="px-5 py-3">
                      <div className="flex justify-end gap-1">
                        <button
                          type="button"
                          className="icon-btn"
                          aria-label={`Modifier ${d.host}`}
                          onClick={() => setEditing(d)}
                        >
                          <PencilSimple size={16} />
                        </button>
                        <button
                          type="button"
                          className="icon-btn"
                          aria-label={`Supprimer ${d.host}`}
                          onClick={() => setDeleting(d)}
                        >
                          <Trash size={16} />
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {editing !== undefined && (
        <DomainForm
          domain={editing ?? undefined}
          onClose={() => setEditing(undefined)}
        />
      )}

      {deleting && (
        <ConfirmDialog
          title="Supprimer le domaine"
          message={`Le domaine ${deleting.host} sera supprime definitivement.`}
          pending={del.isPending}
          onCancel={() => setDeleting(null)}
          onConfirm={() => del.mutate(deleting.id, { onSuccess: () => setDeleting(null) })}
        />
      )}
    </>
  )
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function LiensPage() {
  const [params, setParams] = useSearchParams()
  const tabParam = params.get('tab')
  const tab: Tab = tabParam === 'domaines' ? 'domaines' : 'liens'

  const setTab = (t: Tab) => {
    const next = new URLSearchParams(params)
    if (t === 'liens') next.delete('tab')
    else next.set('tab', t)
    setParams(next, { replace: true })
  }

  const domains = useDomains()

  return (
    <>
      <div className="mb-6 flex gap-1 border-b border-line">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            className={`px-4 py-2 text-[13px] font-semibold transition-colors ${
              tab === t.key
                ? 'border-b-2 border-accent-1 text-white'
                : 'text-muted hover:text-white'
            }`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {domains.isLoading && <Loading />}
      {domains.isError && <ErrorState error={domains.error} onRetry={() => domains.refetch()} />}

      {domains.data && tab === 'liens' && <LinksTab domains={domains.data} />}
      {domains.data && tab === 'domaines' && <DomainsTab domains={domains.data} />}
    </>
  )
}
