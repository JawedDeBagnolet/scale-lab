import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { BatteryFull, DeviceMobile, FloppyDisk, Lightning, Plus, PencilSimple, Trash, WifiHigh } from '@phosphor-icons/react'
import ConfirmDialog from '../../components/ConfirmDialog'
import { Empty, ErrorState, Loading } from '../../components/StateBlock'
import Modal from '../../components/Modal'
import { useDeleteIphone, useIphones, useMarches, useSaveIphone } from '../../hooks/useApi'
import { IPHONE_STATUSES, type IPhone, type IPhoneInput, type IPhoneStatus } from '../../types/iphone'

const STATUS_LABELS: Record<IPhoneStatus, string> = {
  online: 'En ligne',
  offline: 'Hors ligne',
}

const isStatus = (v: string | null): v is IPhoneStatus => IPHONE_STATUSES.includes(v as IPhoneStatus)

function batteryColor(pct: number): string {
  if (pct > 50) return '#22c55e'
  if (pct > 20) return '#f59e0b'
  return '#ef4444'
}

// ---------------------------------------------------------------------------
// IPhone Form (modal)
// ---------------------------------------------------------------------------

function IPhoneForm({ iphone, onClose }: { iphone?: IPhone; onClose: () => void }) {
  const save = useSaveIphone()
  const marches = useMarches()

  const [form, setForm] = useState<IPhoneInput>({
    name: iphone?.name ?? '',
    model: iphone?.model ?? '',
    ios_version: iphone?.ios_version ?? '',
    rack: iphone?.rack ?? null,
    market: iphone?.market ?? null,
    status: iphone?.status ?? 'offline',
    jailbreak: iphone?.jailbreak ?? false,
    max_comptes: iphone?.max_comptes ?? 3,
    proxy_id: iphone?.proxy_id ?? null,
  })

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    save.mutate(
      { id: iphone?.id, data: form },
      { onSuccess: onClose },
    )
  }

  return (
    <Modal
      title={iphone ? `Modifier ${iphone.name}` : 'Nouvel iPhone'}
      onClose={onClose}
      width={540}
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Annuler
          </button>
          <button
            type="submit"
            form="iphone-form"
            className="btn btn-primary"
            disabled={save.isPending || !form.name.trim() || !form.model.trim()}
          >
            <FloppyDisk size={16} /> Enregistrer
          </button>
        </>
      }
    >
      <form id="iphone-form" onSubmit={submit} className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Nom</label>
            <input
              className="field"
              placeholder="iPhone-01"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              autoFocus
            />
          </div>
          <div>
            <label className="label">Modele</label>
            <input
              className="field"
              placeholder="iPhone 12 Pro"
              value={form.model}
              onChange={(e) => setForm({ ...form, model: e.target.value })}
            />
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="label">Version iOS</label>
            <input
              className="field"
              placeholder="16.7.2"
              value={form.ios_version}
              onChange={(e) => setForm({ ...form, ios_version: e.target.value })}
            />
          </div>
          <div>
            <label className="label">Rack</label>
            <input
              className="field"
              placeholder="A1"
              value={form.rack ?? ''}
              onChange={(e) => setForm({ ...form, rack: e.target.value || null })}
            />
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
            <label className="label">Statut</label>
            <select
              className="field"
              value={form.status}
              onChange={(e) => setForm({ ...form, status: e.target.value as IPhoneStatus })}
            >
              {IPHONE_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {STATUS_LABELS[s]}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">Max comptes</label>
            <input
              type="number"
              className="field"
              min={1}
              max={10}
              value={form.max_comptes}
              onChange={(e) => setForm({ ...form, max_comptes: Number(e.target.value) })}
            />
          </div>
          <div className="flex items-end pb-1">
            <label className="flex items-center gap-2 text-[13px]">
              <input
                type="checkbox"
                checked={form.jailbreak}
                onChange={(e) => setForm({ ...form, jailbreak: e.target.checked })}
              />
              Jailbreak
            </label>
          </div>
        </div>
      </form>
    </Modal>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function ParcIphonePage() {
  const [params, setParams] = useSearchParams()
  const statusParam = params.get('status')
  const market = params.get('market') ?? undefined
  const status = isStatus(statusParam) ? statusParam : undefined

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }

  const iphones = useIphones({ status, market })
  const marches = useMarches()
  const del = useDeleteIphone()

  // undefined = ferme, null = creation, IPhone = edition
  const [editing, setEditing] = useState<IPhone | null | undefined>(undefined)
  const [deleting, setDeleting] = useState<IPhone | null>(null)

  const filtered = Boolean(status || market)

  return (
    <>
      <div className="mb-6 flex items-center gap-3">
        <select
          className="field w-40"
          aria-label="Filtrer par statut"
          value={status ?? ''}
          onChange={(e) => setFilter('status', e.target.value)}
        >
          <option value="">Tous les statuts</option>
          {IPHONE_STATUSES.map((s) => (
            <option key={s} value={s}>
              {STATUS_LABELS[s]}
            </option>
          ))}
        </select>
        <select
          className="field w-40"
          aria-label="Filtrer par marche"
          value={market ?? ''}
          onChange={(e) => setFilter('market', e.target.value)}
        >
          <option value="">Tous les marches</option>
          {marches.data?.map((m) => (
            <option key={m.code} value={m.code}>
              {m.label}
            </option>
          ))}
        </select>
        <span className="text-[13px] text-muted">
          {iphones.data ? `${iphones.data.length} iPhone${iphones.data.length > 1 ? 's' : ''}` : ''}
        </span>
        <button type="button" className="btn btn-primary ml-auto" onClick={() => setEditing(null)}>
          <Plus size={16} weight="bold" /> Nouvel iPhone
        </button>
      </div>

      {iphones.isLoading && <Loading />}
      {iphones.isError && <ErrorState error={iphones.error} onRetry={() => iphones.refetch()} />}
      {iphones.data?.length === 0 && (
        <Empty
          action={
            !filtered && (
              <button type="button" className="btn btn-ghost" onClick={() => setEditing(null)}>
                Ajouter le premier iPhone
              </button>
            )
          }
        >
          {filtered
            ? 'Aucun iPhone ne correspond aux filtres.'
            : 'Aucun iPhone pour le moment.'}
        </Empty>
      )}

      <div className="grid grid-cols-3 gap-5 min-[1680px]:grid-cols-4">
        {iphones.data?.map((phone) => {
          const t = phone.telemetry
          const batteryPct = t?.battery_pct
          return (
            <article key={phone.id} className="card flex flex-col gap-4 p-5">
              {/* Header */}
              <div className="flex items-start gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent-1/15">
                  <DeviceMobile size={20} className="text-accent-1" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-base font-bold">{phone.name}</span>
                    <span
                      className="h-2 w-2 shrink-0 rounded-full"
                      style={{ background: phone.status === 'online' ? '#22c55e' : '#555872' }}
                      title={STATUS_LABELS[phone.status]}
                    />
                  </div>
                  <div className="truncate text-[13px] text-muted">
                    {phone.model} &middot; iOS {phone.ios_version}
                  </div>
                </div>
                <button type="button" className="icon-btn" aria-label={`Modifier ${phone.name}`} onClick={() => setEditing(phone)}>
                  <PencilSimple size={16} />
                </button>
                <button type="button" className="icon-btn" aria-label={`Supprimer ${phone.name}`} onClick={() => setDeleting(phone)}>
                  <Trash size={16} />
                </button>
              </div>

              {/* Info tags */}
              <div className="flex flex-wrap gap-1.5 text-xs">
                {phone.rack && (
                  <span className="inline-flex h-6 items-center rounded-lg bg-white/[0.06] px-2 font-medium text-white/70">
                    Rack {phone.rack}
                  </span>
                )}
                {phone.market && (
                  <span className="inline-flex h-6 items-center rounded-lg bg-accent-2/15 px-2 font-medium text-white/80">
                    {phone.market.toUpperCase()}
                  </span>
                )}
                {phone.jailbreak && (
                  <span className="inline-flex h-6 items-center rounded-lg bg-warning/15 px-2 font-medium text-warning">
                    JB
                  </span>
                )}
                <span className="inline-flex h-6 items-center rounded-lg bg-white/[0.06] px-2 font-medium text-white/70">
                  Max {phone.max_comptes} comptes
                </span>
              </div>

              {/* Telemetry */}
              <div className="mt-auto border-t border-line pt-3">
                {t ? (
                  <div className="space-y-2 text-[13px]">
                    {/* Battery bar */}
                    {batteryPct != null && (
                      <div className="flex items-center gap-2">
                        <BatteryFull size={16} className="shrink-0 text-muted" />
                        <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-white/[0.06]">
                          <div
                            className="absolute inset-y-0 left-0 rounded-full transition-all"
                            style={{
                              width: `${batteryPct}%`,
                              background: batteryColor(batteryPct),
                            }}
                          />
                        </div>
                        <span className="w-9 text-right text-muted">{batteryPct}%</span>
                        {t.charging && <Lightning size={14} className="text-warning" />}
                      </div>
                    )}
                    {/* Network */}
                    {t.network_quality && (
                      <div className="flex items-center gap-2 text-muted">
                        <WifiHigh size={16} className="shrink-0" />
                        <span>{t.network_quality}</span>
                        {t.data_used_mb != null && (
                          <span className="ml-auto">{t.data_used_mb.toFixed(0)} Mo</span>
                        )}
                      </div>
                    )}
                    {/* Current run/compte */}
                    {(t.current_run || t.current_compte) && (
                      <div className="flex items-center gap-2 text-muted">
                        <span className="h-1.5 w-1.5 shrink-0 animate-pulse rounded-full bg-success" />
                        <span className="truncate">
                          {t.current_run}
                          {t.current_compte && <span className="text-dim"> &middot; {t.current_compte}</span>}
                        </span>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-[13px] text-dim">Pas de telemetrie</div>
                )}
              </div>
            </article>
          )
        })}
      </div>

      {editing !== undefined && (
        <IPhoneForm iphone={editing ?? undefined} onClose={() => setEditing(undefined)} />
      )}

      {deleting && (
        <ConfirmDialog
          title="Supprimer l'iPhone"
          message={`L'iPhone "${deleting.name}" sera supprime definitivement.`}
          pending={del.isPending}
          onCancel={() => setDeleting(null)}
          onConfirm={() => del.mutate(deleting.id, { onSuccess: () => setDeleting(null) })}
        />
      )}
    </>
  )
}
