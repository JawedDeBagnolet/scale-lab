// ─── Sparkline / chart path generators ──────────────────

function r(n: number) { return Math.round(n * 10) / 10 }

/** Smooth sparkline (Catmull-Rom → cubic Bézier). Returns line + area paths for an SVG viewBox of w×h. */
export function sparkPath(vals: number[], w = 1000, h = 1000, pad = 0.08) {
  if (vals.length < 2) return { line: '', area: '' }
  const mn = Math.min(...vals), mx = Math.max(...vals), rng = mx - mn || 1
  const pts = vals.map((v, i): [number, number] => [
    (i / (vals.length - 1)) * w,
    h * pad + (1 - (v - mn) / rng) * h * (1 - 2 * pad),
  ])
  let d = `M${r(pts[0][0])},${r(pts[0][1])}`
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[Math.max(0, i - 1)]
    const p1 = pts[i]
    const p2 = pts[i + 1]
    const p3 = pts[Math.min(pts.length - 1, i + 2)]
    d += ` C${r(p1[0] + (p2[0] - p0[0]) / 6)},${r(p1[1] + (p2[1] - p0[1]) / 6)} ${r(p2[0] - (p3[0] - p1[0]) / 6)},${r(p2[1] - (p3[1] - p1[1]) / 6)} ${r(p2[0])},${r(p2[1])}`
  }
  return { line: d, area: `${d} L${w},${h} L0,${h} Z` }
}

/** Chart path for revenue-style cumulative chart. vals mapped to 0..maxVal on Y, 0..slots on X. */
export function chartPath(vals: number[], maxVal: number, slots: number, w = 1000, h = 1000, padY = 0.05) {
  if (vals.length < 2) return { line: '', area: '' }
  const pts = vals.map((v, i): [number, number] => [
    (i / slots) * w,
    h - padY * h - (v / maxVal) * h * (1 - 2 * padY),
  ])
  let d = `M${r(pts[0][0])},${r(pts[0][1])}`
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[Math.max(0, i - 1)]
    const p1 = pts[i]
    const p2 = pts[i + 1]
    const p3 = pts[Math.min(pts.length - 1, i + 2)]
    d += ` C${r(p1[0] + (p2[0] - p0[0]) / 6)},${r(p1[1] + (p2[1] - p0[1]) / 6)} ${r(p2[0] - (p3[0] - p1[0]) / 6)},${r(p2[1] - (p3[1] - p1[1]) / 6)} ${r(p2[0])},${r(p2[1])}`
  }
  const lastX = r(pts[pts.length - 1][0])
  return { line: d, area: `${d} L${lastX},${h} L0,${h} Z` }
}

// ─── Formatting ─────────────────────────────────────────

export function fmtN(n: number): string {
  return n.toLocaleString('fr-FR')
}

export function fmtK(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace('.', ',') + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1).replace('.', ',') + 'k'
  return n.toString()
}

export function fmtEur(n: number): string {
  return n.toLocaleString('fr-FR') + ' €'
}

export function todayFR(): string {
  return new Date().toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
}
