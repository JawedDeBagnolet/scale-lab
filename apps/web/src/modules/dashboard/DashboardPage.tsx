import { Link } from 'react-router-dom'
import {
  ArrowRight,
  ChatCircle,
  CheckCircle,
  Coffee,
  Crosshair,
  DeviceMobile,
  Gift,
  Globe,
  InstagramLogo,
  Lightning,

  MoonStars,
  RocketLaunch,
  SlidersHorizontal,
  SquaresFour,
  SunHorizon,
  ThreadsLogo,
  UserCircle,
  UsersThree,
  WarningCircle,
  XLogo,
} from '@phosphor-icons/react'
import { sparkPath, chartPath, todayFR } from './dashboard-utils'

// ─── Colours (match mockup exactly) ───────────────────────────────────────────

const C = {
  main: '#f2f3fa',
  sec: '#e8eaf3',
  med: '#c5c9d8',
  muted: '#8a91a8',
  dim: '#6b7289',
  vdim: '#5b6175',
  icon: '#aab0c5',
  accent: '#cfd3ff',
}

// ─── Shared card style ────────────────────────────────────────────────────────

const CARD: React.CSSProperties = {
  padding: '16px 18px',
  borderRadius: 14,
  border: '1px solid rgba(255,255,255,.07)',
  background: 'rgba(255,255,255,.022)',
  display: 'flex',
  flexDirection: 'column',
  gap: 14,
  minWidth: 0,
}

// ─── Demo data ────────────────────────────────────────────────────────────────

const PERSONAS_DATA = [
  { id: 'lea', first: 'Léa', last: 'Martin', color: '#8b7cf6', market: 'FR', accs: 7, reach: 84000, subs: 12400, ca: 4280, ltv: 18, spark: [12, 14, 13, 16, 18, 17, 20, 22, 24, 23, 26, 28] },
  { id: 'maya', first: 'Maya', last: 'Laurent', color: '#5b8def', market: 'FR', accs: 7, reach: 62000, subs: 8100, ca: 2940, ltv: 14, spark: [15, 14, 16, 15, 17, 16, 18, 17, 19, 18, 20, 19] },
  { id: 'sofia', first: 'Sofia', last: 'Reyes', color: '#2dd4a8', market: 'US', accs: 8, reach: 156000, subs: 22800, ca: 8120, ltv: 24, spark: [20, 24, 28, 32, 38, 42, 48, 54, 60, 68, 72, 80] },
  { id: 'clara', first: 'Clara', last: 'Vidal', color: '#f472b6', market: 'ES', accs: 5, reach: 31000, subs: 4200, ca: 1650, ltv: 11, spark: [18, 20, 19, 17, 16, 15, 14, 13, 12, 11, 10, 9] },
  { id: 'nina', first: 'Nina', last: 'Morel', color: '#f5b04c', market: 'FR', accs: 7, reach: 48000, subs: 6700, ca: 2310, ltv: 15, spark: [8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30] },
  { id: 'alba', first: 'Alba', last: 'Ortega', color: '#38bdf8', market: 'ES', accs: 8, reach: 72000, subs: 9500, ca: 3480, ltv: 16, spark: [22, 24, 23, 26, 28, 27, 30, 32, 31, 34, 36, 35] },
]

const ALERTS_DATA = [
  { Icon: WarningCircle, iconColor: '#fda4af', title: '3 comptes en erreur', sub: 'clara.ntv, nina.zen, sofia.breathe', module: 'Comptes', to: '/comptes' },
  { Icon: Lightning, iconColor: '#f5c77e', title: 'Proxy FR-12 hors ligne', sub: '3 comptes affectés', module: 'Infrastructure', to: '/proxies' },
  { Icon: WarningCircle, iconColor: '#f5c77e', title: 'iPhone #07 hors ligne', sub: 'depuis 2h — 3 comptes en attente', module: 'Parc iPhone', to: '/iphones' },
  { Icon: Lightning, iconColor: '#8db4fd', title: '2 licences expirent bientôt', sub: 'TG Nina #3 · OF lou.xo', module: 'OnlyChat', to: '/parametres' },
]

const KPIS_DATA = [
  { Icon: UserCircle, label: 'Personas', value: '6', delta: '+1', deltaUp: true, sub: '3 marchés · 4 plateformes', spark: [3, 3, 4, 4, 5, 5, 5, 6, 6, 6, 6, 6], color: '#8b7cf6', to: '/personas' },
  { Icon: UsersThree, label: 'Comptes', value: '42', delta: '+3', deltaUp: true, sub: '38 OK · 3 erreur · 1 session', spark: [18, 22, 25, 28, 30, 33, 35, 37, 39, 40, 41, 42], color: '#5b8def', to: '/comptes' },
  { Icon: Crosshair, label: 'Targets', value: '24', delta: null, deltaUp: true, sub: 'suivis par 6 personas', spark: [8, 10, 12, 14, 16, 18, 19, 20, 21, 22, 23, 24], color: '#2dd4a8', to: '/targets' },
  { Icon: SlidersHorizontal, label: 'Presets', value: '9', delta: null, deltaUp: true, sub: '3 X · 3 IG · 2 Threads', spark: [4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 9], color: '#f5b04c', to: '/comportements' },
]

const REV_TODAY = [0, 0, 0, 0, 0, 0, 120, 340, 580, 890, 1250, 1540, 1820, 2100, 2340, 2560, 2700, 2847]
const REV_YESTERDAY = [0, 0, 0, 0, 0, 0, 80, 280, 510, 780, 1100, 1450, 1780, 2050, 2380, 2650, 2890, 3050, 3120, 3150, 3180, 3200, 3205, 3210]
const REV_MAX = 3500
const REV_SLOTS = 24

const SALES_DATA = [
  { persona: 'Léa', color: '#8b7cf6', plat: 'ig' as const, acc: 'lea.fitfr', type: 'Tip', ago: '3 min', amount: '45 €' },
  { persona: 'Sofia', color: '#2dd4a8', plat: 'ig' as const, acc: 'sofia.us.ig', type: 'Message', ago: '8 min', amount: '12 $' },
  { persona: 'Maya', color: '#5b8def', plat: 'th' as const, acc: 'maya.threads', type: 'PPV', ago: '15 min', amount: '28 €' },
  { persona: 'Léa', color: '#8b7cf6', plat: 'ig' as const, acc: 'lea.moves', type: 'Abo', ago: '22 min', amount: '15 €' },
  { persona: 'Nina', color: '#f5b04c', plat: 'ig' as const, acc: 'nina.fr', type: 'Message', ago: '35 min', amount: '8 €' },
]

const HEALTH_ACC = [
  { label: 'Actif', n: 25, color: '#22c55e', pct: 59.5 },
  { label: 'Warmup', n: 8, color: '#f5b04c', pct: 19 },
  { label: 'Onboarding', n: 5, color: '#5b8def', pct: 11.9 },
  { label: 'Pause', n: 4, color: '#6b7289', pct: 9.6 },
]

const IPHONES = [
  { name: 'iPhone #03', ok: true }, { name: 'iPhone #04', ok: true },
  { name: 'iPhone #05', ok: true }, { name: 'iPhone #07', ok: false },
  { name: 'iPhone #08', ok: true }, { name: 'iPhone #09', ok: true },
  { name: 'iPhone #11', ok: false }, { name: 'iPhone #12', ok: true },
  { name: 'iPhone #14', ok: true }, { name: 'iPhone #15', ok: true },
  { name: 'iPhone #16', ok: true }, { name: 'iPhone #18', ok: true },
]

const PROXIES = [
  { name: 'proxy-fr-04', status: 'ok' as const }, { name: 'proxy-fr-08', status: 'ok' as const },
  { name: 'proxy-fr-12', status: 'down' as const }, { name: 'proxy-fr-15', status: 'ok' as const },
  { name: 'proxy-fr-19', status: 'ok' as const }, { name: 'proxy-fr-21', status: 'ok' as const },
  { name: 'proxy-fr-31', status: 'ok' as const }, { name: 'proxy-us-03', status: 'slow' as const },
  { name: 'proxy-us-07', status: 'ok' as const }, { name: 'proxy-us-11', status: 'ok' as const },
  { name: 'proxy-es-02', status: 'ok' as const }, { name: 'proxy-es-07', status: 'ok' as const },
]

const CAMPAIGNS_DATA = [
  { name: 'Léa · Reels du matin', Icon: SunHorizon, persona: 'Léa Martin', plat: 'ig' as const, status: 'active', statusLabel: 'En cours', prog: '72 %', progPct: 72, color: '#8b7cf6' },
  { name: 'Maya · Threads slow life', Icon: Coffee, persona: 'Maya Laurent', plat: 'th' as const, status: 'active', statusLabel: 'En cours', prog: '45 %', progPct: 45, color: '#5b8def' },
  { name: 'Sofia · US launch', Icon: RocketLaunch, persona: 'Sofia Reyes', plat: 'ig' as const, status: 'paused', statusLabel: 'En pause', prog: null, progPct: 0, color: '#2dd4a8' },
  { name: 'Nina · Yoga du soir', Icon: MoonStars, persona: 'Nina Morel', plat: 'ig' as const, status: 'done', statusLabel: 'Terminée', prog: '100 %', progPct: 100, color: '#f5b04c' },
]

const INCIDENTS_DATA = [
  { who: 'clara.ntv', what: 'Session expirée', sub: 'iPhone #16 · Instagram', ago: '12 min', severity: 'error' as const },
  { who: 'proxy-fr-12', what: 'Connexion perdue', sub: '3 comptes affectés', ago: '28 min', severity: 'error' as const },
  { who: 'nina.zen', what: 'Checkpoint Instagram', sub: 'Action requise', ago: '1h', severity: 'warning' as const },
  { who: 'maya.cafe', what: 'Rate limit Threads', sub: 'Pause auto 15 min', ago: '2h', severity: 'warning' as const },
  { who: 'sofia.breathe', what: 'Échec publication', sub: 'Reel non uploadé', ago: '4h', severity: 'info' as const },
  { who: 'proxy-us-03', what: 'Latence élevée', sub: '> 800 ms', ago: '6h', severity: 'info' as const },
]

const TOP_ACC_DATA = [
  { rank: 1, handle: 'lea.fitfr', plat: 'ig' as const, persona: 'Léa Martin', pColor: '#8b7cf6', delta: '+12 %', deltaUp: true, reach: '24,1k' },
  { rank: 2, handle: 'sofia.us.ig', plat: 'ig' as const, persona: 'Sofia Reyes', pColor: '#2dd4a8', delta: '+8 %', deltaUp: true, reach: '41,2k' },
  { rank: 3, handle: 'maya.threads', plat: 'th' as const, persona: 'Maya Laurent', pColor: '#5b8def', delta: '+5 %', deltaUp: true, reach: '18,6k' },
  { rank: 4, handle: 'alba.trip', plat: 'ig' as const, persona: 'Alba Ortega', pColor: '#38bdf8', delta: '+3 %', deltaUp: true, reach: '15,8k' },
  { rank: 5, handle: 'nina.fr', plat: 'ig' as const, persona: 'Nina Morel', pColor: '#f5b04c', delta: '−2 %', deltaUp: false, reach: '12,4k' },
  { rank: 6, handle: 'clara.glow', plat: 'ig' as const, persona: 'Clara Vidal', pColor: '#f472b6', delta: '+1 %', deltaUp: true, reach: '8,7k' },
]

// ─── Helpers ──────────────────────────────────────────────────────────────────

function PlatIcon({ plat, size = 12, color }: { plat: 'ig' | 'th' | 'x'; size?: number; color?: string }) {
  const s: React.CSSProperties = { fontSize: size, flexShrink: 0, ...(color ? { color } : {}) }
  switch (plat) {
    case 'ig': return <InstagramLogo size={size} style={s} />
    case 'th': return <ThreadsLogo size={size} style={s} />
    case 'x': return <XLogo size={size} style={s} />
  }
}

function fmtK(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace('.', ',') + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1).replace('.', ',') + 'k'
  return n.toString()
}

function fmtEur(n: number): string {
  return n.toLocaleString('fr-FR') + ' €'
}

const SEV_DOT: Record<string, string> = {
  error: '#ef4444',
  warning: '#f5b04c',
  info: '#5b8def',
}

const STATUS_PILL: Record<string, React.CSSProperties> = {
  active: { fontSize: 11, fontWeight: 600, color: '#4ade80', background: 'rgba(74,222,128,.12)', padding: '2px 8px', borderRadius: 6, whiteSpace: 'nowrap' },
  paused: { fontSize: 11, fontWeight: 600, color: '#f5b04c', background: 'rgba(245,176,76,.12)', padding: '2px 8px', borderRadius: 6, whiteSpace: 'nowrap' },
  done: { fontSize: 11, fontWeight: 600, color: C.muted, background: 'rgba(255,255,255,.06)', padding: '2px 8px', borderRadius: 6, whiteSpace: 'nowrap' },
}

// ─── Section header link ──────────────────────────────────────────────────────

function SectionLink({ to, label }: { to: string; label: string }) {
  return (
    <Link to={to} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 12, fontWeight: 600, whiteSpace: 'nowrap', color: '#8db4fd', textDecoration: 'none' }}>
      {label}<ArrowRight size={12} />
    </Link>
  )
}

// ─── Background effects ──────────────────────────────────────────────────────

function BgEffects() {
  return (
    <div style={{ position: 'absolute', top: -32, left: -32, right: -32, bottom: -120, zIndex: 0, pointerEvents: 'none', overflow: 'hidden' }}>
      <div style={{ position: 'absolute', inset: 0, backgroundImage: 'radial-gradient(rgba(255,255,255,.035) 1px, transparent 1.3px)', backgroundSize: '22px 22px' }} />
      <div style={{ position: 'absolute', inset: 0, background: 'radial-gradient(1100px 420px at 60% -10%, rgba(99,102,241,.06), transparent 60%)' }} />
    </div>
  )
}

// ─── Dashboard header ─────────────────────────────────────────────────────────

function DashHeader() {
  const mkSegs = ['Tous', 'FR', 'US', 'ES']
  const periodSegs = ['24h', '7j', '30j']
  const segActive: React.CSSProperties = { padding: '5px 12px', borderRadius: 8, fontSize: 12.5, fontWeight: 600, color: C.main, background: 'rgba(255,255,255,.08)', cursor: 'pointer' }
  const segIdle: React.CSSProperties = { padding: '5px 12px', borderRadius: 8, fontSize: 12.5, fontWeight: 500, color: C.muted, cursor: 'pointer' }

  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 24, flexWrap: 'wrap' }}>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 12, color: C.vdim, marginBottom: 6 }}>Workspace France · {todayFR()}</div>
        <div style={{ fontSize: 26, fontWeight: 600, letterSpacing: '-.01em', color: C.main, lineHeight: 1.15 }}>Vue d'ensemble</div>
        <div style={{ fontSize: 13, color: C.muted, marginTop: 5 }}>6 personas · 42 comptes actifs sur 3 marchés</div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        {/* Market segment */}
        <div style={{ display: 'flex', gap: 2, background: 'rgba(255,255,255,.035)', border: '1px solid rgba(255,255,255,.07)', borderRadius: 10, padding: 3 }}>
          {mkSegs.map((s, i) => (
            <div key={s} className={i !== 0 ? 'dash-seg-idle' : undefined} style={i === 0 ? segActive : segIdle}>{s}</div>
          ))}
        </div>
        {/* Period segment */}
        <div style={{ display: 'flex', gap: 2, background: 'rgba(255,255,255,.035)', border: '1px solid rgba(255,255,255,.07)', borderRadius: 10, padding: 3 }}>
          {periodSegs.map((s, i) => (
            <div key={s} className={i !== 0 ? 'dash-seg-idle' : undefined} style={i === 0 ? segActive : segIdle}>{s}</div>
          ))}
        </div>
        {/* Customize button */}
        <div className="dash-customize" style={{ display: 'flex', alignItems: 'center', gap: 7, height: 34, padding: '0 13px', borderRadius: 10, border: '1px solid rgba(255,255,255,.1)', fontSize: 12.5, fontWeight: 600, color: C.sec, cursor: 'pointer', whiteSpace: 'nowrap' }}>
          <SquaresFour size={14} />Personnaliser
        </div>
      </div>
    </div>
  )
}

// ─── Alerts row ───────────────────────────────────────────────────────────────

function AlertsRow() {
  if (ALERTS_DATA.length === 0) {
    return (
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(300px,1fr))', gap: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 14px', borderRadius: 12, border: '1px solid rgba(74,222,128,.25)', background: 'rgba(74,222,128,.05)', fontSize: 12.5, color: '#c9f5da' }}>
          <CheckCircle size={17} style={{ color: '#4ade80' }} />Rien à signaler
        </div>
      </div>
    )
  }
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(300px,1fr))', gap: 10 }}>
      {ALERTS_DATA.map((a, i) => (
        <Link key={i} to={a.to} className="dash-alert" style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 14px', borderRadius: 12, border: '1px solid rgba(255,255,255,.07)', background: 'rgba(255,255,255,.022)', color: 'inherit', textDecoration: 'none' }}>
          <a.Icon size={16} style={{ fontSize: 16, flexShrink: 0, color: a.iconColor }} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 12.5, fontWeight: 600, color: C.main, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.title}</div>
            <div style={{ fontSize: 11.5, color: C.muted, marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.sub}</div>
          </div>
          <span style={{ fontSize: 11, color: C.dim, whiteSpace: 'nowrap' }}>{a.module}</span>
        </Link>
      ))}
    </div>
  )
}

// ─── Stats grid (4 KPI cards with sparklines) ─────────────────────────────────

function StatsGrid() {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,minmax(0,1fr))', gap: 12 }}>
      {KPIS_DATA.map((k) => {
        const sp = sparkPath(k.spark)
        return (
          <Link key={k.label} to={k.to} className="dash-kpi" style={{ display: 'flex', flexDirection: 'column', gap: 7, padding: '14px 15px 10px', borderRadius: 14, border: '1px solid rgba(255,255,255,.07)', background: 'rgba(255,255,255,.022)', minWidth: 0, color: 'inherit', textDecoration: 'none' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 12, color: C.muted }}>
              <k.Icon size={14} />
              {k.label}
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
              <span style={{ fontSize: 24, fontWeight: 600, color: C.main, letterSpacing: '-.01em', fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>{k.value}</span>
              {k.delta && (
                <span style={{ fontSize: 12, fontWeight: 600, color: k.deltaUp ? '#4ade80' : '#f87171', background: k.deltaUp ? 'rgba(74,222,128,.12)' : 'rgba(248,113,113,.12)', padding: '2px 8px', borderRadius: 6 }}>{k.delta}</span>
              )}
            </div>
            <div style={{ fontSize: 11.5, color: C.dim, lineHeight: 1.4 }}>{k.sub}</div>
            <svg viewBox="0 0 1000 1000" preserveAspectRatio="none" style={{ width: '100%', height: 34, overflow: 'visible', marginTop: 2 }}>
              <path d={sp.area} fill={k.color} fillOpacity={0.12} />
              <path d={sp.line} fill="none" stroke={k.color} strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </Link>
        )
      })}
    </div>
  )
}

// ─── Revenue card ─────────────────────────────────────────────────────────────

function RevenueCard() {
  const todayP = chartPath(REV_TODAY, REV_MAX, REV_SLOTS)
  const yesterdayP = chartPath(REV_YESTERDAY, REV_MAX, REV_SLOTS)

  // Y-axis ticks
  const yTicks = [
    { label: '3k €', pct: 14.3 },
    { label: '2k €', pct: 42.9 },
    { label: '1k €', pct: 71.4 },
    { label: '0 €', pct: 100 },
  ]
  // X-axis ticks
  const xTicks = [
    { label: '0h', pct: 0 },
    { label: '6h', pct: 25 },
    { label: '12h', pct: 50 },
    { label: '18h', pct: 75 },
    { label: '24h', pct: 100 },
  ]

  // Now dot: last point of today's data
  const nowIdx = REV_TODAY.length - 1
  const nowX = (nowIdx / REV_SLOTS) * 100
  const nowY = 100 - 5 - (REV_TODAY[nowIdx] / REV_MAX) * 90

  return (
    <div style={CARD}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: C.main }}>Revenus OnlyChat aujourd'hui</div>
          <div style={{ fontSize: 12, color: C.muted, marginTop: 3 }}>Cumulé depuis minuit · toutes personas</div>
        </div>
        <SectionLink to="/crm" label="CRM" />
      </div>

      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 30, fontWeight: 600, color: C.main, letterSpacing: '-.01em', fontVariantNumeric: 'tabular-nums' }}>2 847 €</span>
        <span style={{ fontSize: 12, fontWeight: 600, color: '#f87171', background: 'rgba(248,113,113,.12)', padding: '2px 8px', borderRadius: 6 }}>−11,3 %</span>
        <span style={{ fontSize: 12, color: C.muted }}>vs hier à cette heure (3 210 €)</span>
      </div>

      {/* Chart area */}
      <div style={{ display: 'grid', gridTemplateColumns: '44px minmax(0,1fr)', gap: 8 }}>
        {/* Y-axis labels */}
        <div style={{ position: 'relative', height: 170 }}>
          {yTicks.map((t) => (
            <div key={t.label} style={{ position: 'absolute', top: `${t.pct}%`, right: 0, transform: 'translateY(-50%)', fontSize: 10.5, color: C.dim, fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>{t.label}</div>
          ))}
        </div>
        {/* Chart */}
        <div>
          <div style={{ position: 'relative', height: 170 }}>
            {/* Grid lines */}
            {yTicks.map((t) => (
              <div key={t.label} style={{ position: 'absolute', top: `${t.pct}%`, left: 0, right: 0, height: 0, borderTop: '1px solid rgba(255,255,255,.05)' }} />
            ))}
            {/* SVG paths */}
            <svg viewBox="0 0 1000 1000" preserveAspectRatio="none" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', overflow: 'visible' }}>
              <path d={yesterdayP.line} fill="none" stroke={C.dim} strokeWidth={2} strokeDasharray="8 6" strokeLinecap="round" />
              <path d={todayP.area} fill="#8b7cf6" fillOpacity={0.1} />
              <path d={todayP.line} fill="none" stroke="#8b7cf6" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            {/* Now dot */}
            <div style={{ position: 'absolute', left: `${nowX}%`, top: `${nowY}%`, width: 8, height: 8, borderRadius: '50%', background: '#8b7cf6', boxShadow: '0 0 8px rgba(139,124,246,.5)', transform: 'translate(-50%,-50%)' }} />
          </div>
          {/* X-axis labels */}
          <div style={{ position: 'relative', height: 18, marginTop: 6 }}>
            {xTicks.map((t) => (
              <div key={t.label} style={{ position: 'absolute', left: `${t.pct}%`, transform: 'translateX(-50%)', fontSize: 10.5, color: C.dim }}>{t.label}</div>
            ))}
          </div>
        </div>
      </div>

      {/* Legend + split */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap', fontSize: 12, color: C.med }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
          <span style={{ width: 14, height: 3, borderRadius: 99, background: '#8b7cf6' }} />Aujourd'hui
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
          <span style={{ width: 14, height: 0, borderTop: '2px dashed #6b7289' }} />Hier
        </span>
        <span style={{ flex: 1 }} />
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <ChatCircle size={13} style={{ color: C.icon }} />Messages
          <span style={{ color: C.main, fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>1 520 €</span>
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Gift size={13} style={{ color: C.icon }} />Tips
          <span style={{ color: C.main, fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>847 €</span>
        </span>
      </div>

      {/* Dernières ventes */}
      <div style={{ display: 'flex', flexDirection: 'column', borderTop: '1px solid rgba(255,255,255,.06)' }}>
        <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '.1em', textTransform: 'uppercase', color: C.muted, padding: '12px 0 6px' }}>Dernières ventes</div>
        {SALES_DATA.map((x, i) => (
          <div key={i} style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) auto auto', gap: 12, alignItems: 'center', padding: '8px 0', borderTop: '1px solid rgba(255,255,255,.04)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 9, minWidth: 0 }}>
              <span style={{ width: 7, height: 7, borderRadius: '50%', background: x.color, flexShrink: 0 }} />
              <span style={{ fontSize: 12.5, color: C.sec, whiteSpace: 'nowrap' }}>{x.persona}</span>
              <PlatIcon plat={x.plat} size={12} />
              <span style={{ fontSize: 12, color: C.muted, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{x.acc} · {x.type}</span>
            </div>
            <span style={{ fontSize: 11.5, color: C.dim, whiteSpace: 'nowrap' }}>{x.ago}</span>
            <span style={{ minWidth: 64, textAlign: 'right', fontSize: 13, fontWeight: 600, color: C.main, fontVariantNumeric: 'tabular-nums' }}>{x.amount}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── Health card ──────────────────────────────────────────────────────────────

function HealthCard() {
  const onlineIphones = IPHONES.filter((d) => d.ok).length
  const offlineIphones = IPHONES.filter((d) => !d.ok)
  const downProxies = PROXIES.filter((p) => p.status === 'down')
  const slowProxies = PROXIES.filter((p) => p.status === 'slow')

  return (
    <div style={CARD}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: C.main }}>Santé du parc</div>
          <div style={{ fontSize: 12, color: C.muted, marginTop: 3 }}>12 iPhones · 12 proxies · 42 comptes</div>
        </div>
        <SectionLink to="/comptes" label="Comptes" />
      </div>

      {/* Account status */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
          <span style={{ fontSize: 12.5, fontWeight: 600, color: C.sec }}>Comptes</span>
          <span style={{ fontSize: 12, color: C.muted, fontVariantNumeric: 'tabular-nums' }}>42</span>
        </div>
        {/* Stacked bar */}
        <div style={{ display: 'flex', height: 10, borderRadius: 99, overflow: 'hidden', gap: 2 }}>
          {HEALTH_ACC.map((x) => (
            <div key={x.label} style={{ flex: x.pct, background: x.color, borderRadius: 99 }} />
          ))}
        </div>
        {/* Legend */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2,minmax(0,1fr))', gap: '6px 14px' }}>
          {HEALTH_ACC.map((x) => (
            <div key={x.label} style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 12 }}>
              <span style={{ width: 7, height: 7, borderRadius: '50%', background: x.color, flexShrink: 0 }} />
              <span style={{ flex: 1, color: C.med }}>{x.label}</span>
              <span style={{ color: C.main, fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>{x.n}</span>
            </div>
          ))}
        </div>
        {/* Workflow tags */}
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {['Actif', 'Warmup', 'Onboarding', 'Pause'].map((w) => (
            <span key={w} style={{ fontSize: 11, color: C.icon, padding: '2px 8px', borderRadius: 99, background: 'rgba(255,255,255,.05)' }}>{w}</span>
          ))}
        </div>
      </div>

      {/* iPhone block */}
      <Link to="/iphones" style={{ display: 'flex', flexDirection: 'column', gap: 8, paddingTop: 12, borderTop: '1px solid rgba(255,255,255,.06)', color: 'inherit', textDecoration: 'none' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <DeviceMobile size={15} style={{ color: C.icon }} />
          <span style={{ flex: 1, fontSize: 12.5, fontWeight: 600, color: C.sec }}>iPhones</span>
          <span style={{ fontSize: 12, color: C.med, fontVariantNumeric: 'tabular-nums' }}>12</span>
          <span style={{ fontSize: 11, fontWeight: 600, color: onlineIphones === IPHONES.length ? '#4ade80' : '#f5b04c', background: onlineIphones === IPHONES.length ? 'rgba(74,222,128,.12)' : 'rgba(245,176,76,.12)', padding: '2px 8px', borderRadius: 6 }}>
            {onlineIphones} en ligne
          </span>
        </div>
        <div style={{ display: 'flex', gap: 3 }}>
          {IPHONES.map((d) => (
            <span key={d.name} title={d.name} style={{ width: 18, height: 18, borderRadius: 4, background: d.ok ? 'rgba(34,197,94,.25)' : 'rgba(239,68,68,.25)' }} />
          ))}
        </div>
        {offlineIphones.map((d) => (
          <div key={d.name} style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 12, color: C.med }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#ef4444', flexShrink: 0 }} />
            <span style={{ fontFamily: "'Geist Mono', monospace", fontSize: 11.5, color: C.sec }}>{d.name}</span>
            <span style={{ color: C.muted }}>hors ligne</span>
          </div>
        ))}
      </Link>

      {/* Proxy block */}
      <Link to="/proxies" style={{ display: 'flex', flexDirection: 'column', gap: 8, paddingTop: 12, borderTop: '1px solid rgba(255,255,255,.06)', color: 'inherit', textDecoration: 'none' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Globe size={15} style={{ color: C.icon }} />
          <span style={{ flex: 1, fontSize: 12.5, fontWeight: 600, color: C.sec }}>Proxies</span>
          <span style={{ fontSize: 12, color: C.med, fontVariantNumeric: 'tabular-nums' }}>12</span>
          <span style={{ fontSize: 11, fontWeight: 600, color: downProxies.length ? '#fda4af' : '#4ade80', background: downProxies.length ? 'rgba(253,164,175,.12)' : 'rgba(74,222,128,.12)', padding: '2px 8px', borderRadius: 6 }}>
            {downProxies.length ? `${downProxies.length} hors ligne` : 'Tous OK'}
          </span>
        </div>
        <div style={{ display: 'flex', gap: 3 }}>
          {PROXIES.map((p) => (
            <span key={p.name} title={p.name} style={{ width: 18, height: 18, borderRadius: 4, background: p.status === 'ok' ? 'rgba(34,197,94,.25)' : p.status === 'down' ? 'rgba(239,68,68,.25)' : 'rgba(245,176,76,.25)' }} />
          ))}
        </div>
        {downProxies.map((p) => (
          <div key={p.name} style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 12, color: C.med }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#ef4444', flexShrink: 0 }} />
            <span style={{ fontFamily: "'Geist Mono', monospace", fontSize: 11.5, color: C.sec }}>{p.name}</span>
            <span style={{ color: C.muted }}>hors ligne</span>
          </div>
        ))}
        {slowProxies.map((p) => (
          <div key={p.name} style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 12, color: C.med }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#f5b04c', flexShrink: 0 }} />
            <span style={{ fontFamily: "'Geist Mono', monospace", fontSize: 11.5, color: C.sec }}>{p.name}</span>
            <span style={{ color: C.muted }}>latence élevée</span>
          </div>
        ))}
      </Link>
    </div>
  )
}

// ─── Campaigns card ───────────────────────────────────────────────────────────

function CampaignsCard() {
  return (
    <div style={CARD}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: C.main }}>Campagnes de posting</div>
          <div style={{ fontSize: 12, color: C.muted, marginTop: 3 }}>2 actives · 1 en pause · 1 terminée</div>
        </div>
        <SectionLink to="/posting" label="Posting" />
      </div>

      {CAMPAIGNS_DATA.map((c) => (
        <div key={c.name} style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: '12px 0 2px', borderTop: '1px solid rgba(255,255,255,.05)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ width: 32, height: 32, borderRadius: 10, display: 'flex', alignItems: 'center', justifyContent: 'center', background: `${c.color}18`, color: c.color, flexShrink: 0 }}>
              <c.Icon size={15} />
            </span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: C.main, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.name}</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11.5, color: C.muted, marginTop: 2 }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: c.color, flexShrink: 0 }} />
                {c.persona}
                <PlatIcon plat={c.plat} size={12} />
              </div>
            </div>
            <span style={STATUS_PILL[c.status]}>{c.statusLabel}</span>
          </div>
          {c.prog && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, paddingLeft: 42 }}>
              <div style={{ flex: 1, height: 5, borderRadius: 99, background: 'rgba(255,255,255,.06)', overflow: 'hidden' }}>
                <div style={{ width: `${c.progPct}%`, height: '100%', borderRadius: 99, background: c.status === 'done' ? C.muted : c.color }} />
              </div>
              <span style={{ fontSize: 11.5, color: C.med, fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>{c.prog}</span>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

// ─── Incidents card ───────────────────────────────────────────────────────────

function IncidentsCard() {
  return (
    <div style={CARD}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: C.main }}>Derniers incidents</div>
          <div style={{ fontSize: 12, color: C.muted, marginTop: 3 }}>6 incidents · 2 critiques</div>
        </div>
        <SectionLink to="/logs" label="Logs" />
      </div>

      {INCIDENTS_DATA.map((x, i) => (
        <div key={i} style={{ display: 'grid', gridTemplateColumns: 'auto minmax(0,1fr) auto', gap: 10, alignItems: 'flex-start', padding: '10px 0', borderTop: '1px solid rgba(255,255,255,.05)' }}>
          <span style={{ width: 7, height: 7, borderRadius: '50%', background: SEV_DOT[x.severity], marginTop: 5, flexShrink: 0 }} />
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 12.5, color: C.sec }}>
              <span style={{ fontFamily: "'Geist Mono', monospace", fontSize: 12 }}>{x.who}</span> · {x.what}
            </div>
            <div style={{ fontSize: 11.5, color: C.muted, marginTop: 2 }}>{x.sub}</div>
          </div>
          <span style={{ fontSize: 11.5, color: C.dim, whiteSpace: 'nowrap' }}>{x.ago}</span>
        </div>
      ))}
    </div>
  )
}

// ─── Personas table ───────────────────────────────────────────────────────────

function PersonasTable() {
  const headStyle: React.CSSProperties = { fontSize: 11, fontWeight: 600, letterSpacing: '.06em', textTransform: 'uppercase', color: C.dim, padding: '8px 0' }
  const cellStyle: React.CSSProperties = { fontSize: 12.5, color: C.med, fontVariantNumeric: 'tabular-nums', padding: '10px 0', borderTop: '1px solid rgba(255,255,255,.04)' }
  const cellBold: React.CSSProperties = { ...cellStyle, color: C.main, fontWeight: 600 }

  return (
    <div style={CARD}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: C.main }}>Personas</div>
          <div style={{ fontSize: 12, color: C.muted, marginTop: 3 }}>Performances 30 jours</div>
        </div>
        <SectionLink to="/statistiques" label="Statistiques" />
      </div>

      <div style={{ overflowX: 'auto' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(150px,1fr) 70px 70px 104px 90px 70px 90px', gap: '0 14px', alignItems: 'center', minWidth: 700 }}>
          {/* Headers */}
          <div style={headStyle}>Persona</div>
          <div style={headStyle}>Comptes</div>
          <div style={headStyle}>Reach</div>
          <div style={headStyle}>Abonnés</div>
          <div style={headStyle}>CA</div>
          <div style={headStyle}>LTV</div>
          <div style={headStyle}>7j</div>

          {/* Rows */}
          {PERSONAS_DATA.map((p) => {
            const sp = sparkPath(p.spark, 100, 30, 0.1)
            const trend = p.spark[p.spark.length - 1] >= p.spark[0]
            return [
              <div key={`${p.id}-name`} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 0', borderTop: '1px solid rgba(255,255,255,.04)' }}>
                <span style={{ width: 30, height: 30, borderRadius: 10, display: 'flex', alignItems: 'center', justifyContent: 'center', background: `${p.color}20`, color: p.color, fontSize: 13, fontWeight: 700, flexShrink: 0 }}>{p.first[0]}</span>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: C.main }}>{p.first} {p.last}</div>
                  <div style={{ fontSize: 11, color: C.dim, marginTop: 1 }}>{p.market}</div>
                </div>
              </div>,
              <div key={`${p.id}-accs`} style={cellStyle}>{p.accs}</div>,
              <div key={`${p.id}-reach`} style={cellStyle}>{fmtK(p.reach)}</div>,
              <div key={`${p.id}-subs`} style={cellStyle}>{fmtK(p.subs)}</div>,
              <div key={`${p.id}-ca`} style={cellBold}>{fmtEur(p.ca)}</div>,
              <div key={`${p.id}-ltv`} style={cellStyle}>{p.ltv} €</div>,
              <div key={`${p.id}-spark`} style={cellStyle}>
                <svg viewBox="0 0 100 30" preserveAspectRatio="none" style={{ width: 84, height: 24, overflow: 'visible' }}>
                  <path d={sp.line} fill="none" stroke={trend ? '#4ade80' : '#f87171'} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </div>,
            ]
          })}
        </div>
      </div>
    </div>
  )
}

// ─── Top accounts card ────────────────────────────────────────────────────────

function TopAccountsCard() {
  return (
    <div style={CARD}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: C.main }}>Meilleurs comptes</div>
          <div style={{ fontSize: 12, color: C.muted, marginTop: 3 }}>Reach 7 jours</div>
        </div>
        <SectionLink to="/comptes" label="Comptes" />
      </div>

      {TOP_ACC_DATA.map((a) => (
        <div key={a.handle} style={{ display: 'grid', gridTemplateColumns: '20px minmax(0,1fr) auto auto', gap: 10, alignItems: 'center', padding: '9px 0', borderTop: '1px solid rgba(255,255,255,.05)' }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: C.dim, fontVariantNumeric: 'tabular-nums' }}>{a.rank}</span>
          <div style={{ minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12.5, color: C.main }}>
              <PlatIcon plat={a.plat} size={13} color={C.icon} />
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>@{a.handle}</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: C.muted, marginTop: 2 }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: a.pColor, flexShrink: 0 }} />
              {a.persona}
            </div>
          </div>
          <span style={{ fontSize: 12, fontWeight: 600, color: a.deltaUp ? '#4ade80' : '#f87171' }}>{a.delta}</span>
          <span style={{ minWidth: 56, textAlign: 'right', fontSize: 13, fontWeight: 600, color: C.main, fontVariantNumeric: 'tabular-nums' }}>{a.reach}</span>
        </div>
      ))}
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  return (
    <div style={{ position: 'relative' }}>
      <BgEffects />

      <div style={{ position: 'relative', zIndex: 1, display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 1480, paddingBottom: 88 }}>
        <DashHeader />
        <AlertsRow />
        <StatsGrid />

        {/* Revenue + Health */}
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1.55fr) minmax(0,1fr)', gap: 14, alignItems: 'start' }}>
          <RevenueCard />
          <HealthCard />
        </div>

        {/* Campaigns + Incidents */}
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) minmax(0,1fr)', gap: 14, alignItems: 'start' }}>
          <CampaignsCard />
          <IncidentsCard />
        </div>

        {/* Personas + Top accounts */}
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,2fr) minmax(280px,1fr)', gap: 14, alignItems: 'start' }}>
          <PersonasTable />
          <TopAccountsCard />
        </div>
      </div>
    </div>
  )
}
