import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { FloppyDisk, PencilSimple, Plus, Trash } from '@phosphor-icons/react'
import ConfirmDialog from '../../components/ConfirmDialog'
import Modal from '../../components/Modal'
import { Empty, ErrorState, Loading } from '../../components/StateBlock'
import { useDeleteProxy, useProxies, useSaveProxy } from '../../hooks/useApi'
import {
  PROXY_STATUSES,
  PROXY_TYPES,
  type Proxy,
  type ProxyInput,
  type ProxyStatus,
  type ProxyType,
} from '../../types/proxy'

const STATUS_COLORS: Record<ProxyStatus, string> = {
  online: '#22c55e',
  offline: '#8b8fa3',
  error: '#ef4444',
}

const STATUS_LABELS: Record<ProxyStatus, string> = {
  online: 'Online',
  offline: 'Offline',
  error: 'Erreur',
}

const isStatus = (v: string | null): v is ProxyStatus =>
  PROXY_STATUSES.includes(v as ProxyStatus)

// ---------------------------------------------------------------------------
// ProxyForm (inline modal)
// ---------------------------------------------------------------------------

function ProxyForm({ proxy, onClose }: { proxy?: Proxy; onClose: () => void }) {
  const save = useSaveProxy()

  const [form, setForm] = useState<ProxyInput>({
    pool: proxy?.pool ?? '',
    type: proxy?.type ?? '4G',
    iphone_id: proxy?.iphone_id ?? null,
    ip: proxy?.ip ?? '',
    country: proxy?.country ?? '',
    latency_ms: proxy?.latency_ms ?? null,
    status: proxy?.status ?? 'online',
    blacklists: proxy?.blacklists ?? [],
    availability_7d: proxy?.availability_7d ?? 1.0,
  })

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    save.mutate({ id: proxy?.id, data: form }, { onSuccess: onClose })
  }

  return (
    <Modal
      title={proxy ? `Modifier le proxy ${proxy.ip}` : 'Ajouter un proxy'}
      onClose={onClose}
      width={540}
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Annuler
          </button>
          <button
            type="submit"
            form="proxy-form"
            className="btn btn-primary"
            disabled={save.isPending || !form.ip.trim() || !form.pool.trim()}
          >
            <FloppyDisk size={16} /> Enregistrer
          </button>
        </>
      }
    >
      <form id="proxy-form" onSubmit={submit} className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Pool</label>
            <input
              className="field"
              placeholder="fr_ig"
              value={form.pool}
              onChange={(e) => setForm({ ...form, pool: e.target.value })}
              autoFocus
            />
          </div>
          <div>
            <label className="label">Type</label>
            <select
              className="field"
              value={form.type}
              onChange={(e) => setForm({ ...form, type: e.target.value as ProxyType })}
            >
              {PROXY_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Adresse IP</label>
            <input
              className="field"
              placeholder="192.168.1.1"
              value={form.ip}
              onChange={(e) => setForm({ ...form, ip: e.target.value })}
            />
          </div>
          <div>
            <label className="label">Pays</label>
            <input
              className="field"
              placeholder="FR"
              value={form.country}
              onChange={(e) => setForm({ ...form, country: e.target.value.toUpperCase() })}
              maxLength={5}
            />
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="label">Latence (ms)</label>
            <input
              className="field"
              type="number"
              placeholder="—"
              value={form.latency_ms ?? ''}
              onChange={(e) =>
                setForm({ ...form, latency_ms: e.target.value ? Number(e.target.value) : null })
              }
            />
          </div>
          <div>
            <label className="label">Statut</label>
            <select
              className="field"
              value={form.status}
              onChange={(e) => setForm({ ...form, status: e.target.value as ProxyStatus })}
            >
              {PROXY_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {STATUS_LABELS[s]}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">Disponibilite (%)</label>
            <input
              className="field"
              type="number"
              min={0}
              max={100}
              step={1}
              value={Math.round(form.availability_7d * 100)}
              onChange={(e) =>
                setForm({ ...form, availability_7d: Number(e.target.value) / 100 })
              }
            />
          </div>
        </div>

        <div>
          <label className="label">iPhone ID</label>
          <input
            className="field"
            placeholder="UUID (optionnel)"
            value={form.iphone_id ?? ''}
            onChange={(e) => setForm({ ...form, iphone_id: e.target.value || null })}
          />
        </div>
      </form>
    </Modal>
  )
}

// ---------------------------------------------------------------------------
// ProxiesPage
// ---------------------------------------------------------------------------

export default function ProxiesPage() {
  const [params, setParams] = useSearchParams()
  const poolParam = params.get('pool') ?? undefined
  const statusParam = params.get('status')
  const status = isStatus(statusParam) ? statusParam : undefined

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }

  const proxies = useProxies({ pool: poolParam, status })
  const del = useDeleteProxy()

  const [editing, setEditing] = useState<Proxy | null | undefined>(undefined)
  const [deleting, setDeleting] = useState<Proxy | null>(null)

  // Collect unique pools from data for the filter dropdown
  const pools = [...new Set(proxies.data?.map((p) => p.pool) ?? [])].sort()

  const filtered = Boolean(poolParam || status)

  return (
    <>
      <div className="mb-6 flex items-center gap-3">
        <select
          className="field w-48"
          aria-label="Filtrer par pool"
          value={poolParam ?? ''}
          onChange={(e) => setFilter('pool', e.target.value)}
        >
          <option value="">Tous les pools</option>
          {pools.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        <select
          className="field w-40"
          aria-label="Filtrer par statut"
          value={status ?? ''}
          onChange={(e) => setFilter('status', e.target.value)}
        >
          <option value="">Tous les statuts</option>
          {PROXY_STATUSES.map((s) => (
            <option key={s} value={s}>
              {STATUS_LABELS[s]}
            </option>
          ))}
        </select>
        <span className="text-[13px] text-muted">
          {proxies.data ? `${proxies.data.length} proxy${proxies.data.length > 1 ? 's' : ''}` : ''}
        </span>
        <div className="ml-auto flex gap-2">
          <button type="button" className="btn btn-primary" onClick={() => setEditing(null)}>
            <Plus size={16} weight="bold" /> Ajouter un proxy
          </button>
        </div>
      </div>

      {proxies.isLoading && <Loading />}
      {proxies.isError && <ErrorState error={proxies.error} onRetry={() => proxies.refetch()} />}
      {proxies.data?.length === 0 && (
        <Empty>
          {filtered
            ? 'Aucun proxy ne correspond aux filtres.'
            : 'Aucun proxy pour le moment.'}
        </Empty>
      )}

      {proxies.data && proxies.data.length > 0 && (
        <div className="card overflow-hidden">
          <table className="w-full text-left text-[13px]">
            <thead>
              <tr className="border-b border-line text-[11px] uppercase tracking-wider text-muted">
                <th className="px-5 py-3 font-semibold">Pool</th>
                <th className="px-5 py-3 font-semibold">Type</th>
                <th className="px-5 py-3 font-semibold">IP</th>
                <th className="px-5 py-3 font-semibold">Pays</th>
                <th className="px-5 py-3 font-semibold">Latence</th>
                <th className="px-5 py-3 font-semibold">Statut</th>
                <th className="px-5 py-3 font-semibold">Disponibilite</th>
                <th className="w-24 px-5 py-3" />
              </tr>
            </thead>
            <tbody>
              {proxies.data.map((p) => (
                <tr
                  key={p.id}
                  className="border-b border-line last:border-0 hover:bg-white/[0.02]"
                >
                  <td className="px-5 py-3 font-semibold">{p.pool}</td>
                  <td className="px-5 py-3 text-muted">{p.type}</td>
                  <td className="px-5 py-3 font-mono text-[12px]">{p.ip}</td>
                  <td className="px-5 py-3 text-muted">{p.country}</td>
                  <td className="px-5 py-3 text-muted">
                    {p.latency_ms != null ? `${p.latency_ms} ms` : '—'}
                  </td>
                  <td className="px-5 py-3">
                    <span className="inline-flex items-center gap-2">
                      <span
                        className="h-2 w-2 rounded-full"
                        style={{ background: STATUS_COLORS[p.status] }}
                      />
                      {STATUS_LABELS[p.status] ?? p.status}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-muted">
                    {Math.round(p.availability_7d * 100)}%
                  </td>
                  <td className="px-5 py-3">
                    <div className="flex justify-end gap-1">
                      <button
                        type="button"
                        className="icon-btn"
                        aria-label={`Modifier ${p.ip}`}
                        onClick={() => setEditing(p)}
                      >
                        <PencilSimple size={16} />
                      </button>
                      <button
                        type="button"
                        className="icon-btn"
                        aria-label={`Supprimer ${p.ip}`}
                        onClick={() => setDeleting(p)}
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
        <ProxyForm proxy={editing ?? undefined} onClose={() => setEditing(undefined)} />
      )}

      {deleting && (
        <ConfirmDialog
          title="Supprimer le proxy"
          message={`Le proxy ${deleting.ip} (${deleting.pool}) sera supprime definitivement.`}
          pending={del.isPending}
          onCancel={() => setDeleting(null)}
          onConfirm={() => del.mutate(deleting.id, { onSuccess: () => setDeleting(null) })}
        />
      )}
    </>
  )
}
