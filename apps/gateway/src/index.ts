import { Hono } from 'hono'
import { cors } from 'hono/cors'

type Env = {
  API_BASE: string
  API_SECRET: string
  LOGIN_PASSWORD: string
  CACHE: KVNamespace
  MEDIA: R2Bucket
}

const app = new Hono<{ Bindings: Env }>()

// CORS
app.use('*', cors({
  origin: ['https://scalelab.win', 'http://localhost:5173'],
  allowMethods: ['GET', 'POST', 'PATCH', 'PUT', 'DELETE', 'OPTIONS'],
  allowHeaders: ['Content-Type', 'Authorization'],
  maxAge: 86400,
}))

// ── Login : echange un mot de passe contre le token API ───────────
// POST /auth/login  {password}  →  {token}
// Route hors /api/* donc pas soumise au middleware Bearer.
app.post('/auth/login', async (c) => {
  if (!c.env.LOGIN_PASSWORD) {
    return c.json({ error: 'login not configured' }, 500)
  }
  let body: { password?: string }
  try { body = await c.req.json() } catch { return c.json({ error: 'invalid json' }, 400) }
  const pw = body?.password ?? ''

  // Timing-safe compare via Web Crypto
  const enc = new TextEncoder()
  const a = enc.encode(pw)
  const b = enc.encode(c.env.LOGIN_PASSWORD)
  if (a.byteLength !== b.byteLength) {
    return c.json({ error: 'invalid password' }, 401)
  }
  const ka = await crypto.subtle.importKey('raw', a, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign'])
  const kb = await crypto.subtle.importKey('raw', b, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign'])
  const msg = enc.encode('scalelab-auth-check')
  const [sa, sb] = await Promise.all([
    crypto.subtle.sign('HMAC', ka, msg),
    crypto.subtle.sign('HMAC', kb, msg),
  ])
  const va = new Uint8Array(sa)
  const vb = new Uint8Array(sb)
  let eq = 1
  for (let i = 0; i < va.length; i++) eq &= (va[i] === vb[i] ? 1 : 0)
  if (!eq) {
    return c.json({ error: 'invalid password' }, 401)
  }

  return c.json({ token: c.env.API_SECRET })
})

// Auth : verifie le token de l'app
app.use('/api/*', async (c, next) => {
  // Secret absent (wrangler secret put oublie) : on refuse tout plutot que de
  // comparer undefined === undefined
  if (!c.env.API_SECRET) {
    return c.json({ error: 'gateway misconfigured' }, 500)
  }
  const token = c.req.header('Authorization')?.replace('Bearer ', '')
  if (token !== c.env.API_SECRET) {
    return c.json({ error: 'unauthorized' }, 401)
  }
  await next()
})

// ── KV Edge Cache pour endpoints lents ────────────────────────────
// GET  → sert depuis KV si present (TTL 5 min), sinon proxy + stocke
// POST/PATCH/PUT/DELETE → invalide le cache de l'endpoint
const CACHED_PREFIXES = ['/api/niches', '/api/marches', '/api/settings', '/api/presets']
const KV_TTL = 300 // 5 minutes

function cacheKeyFor(pathname: string): string | null {
  for (const prefix of CACHED_PREFIXES) {
    if (pathname === prefix || pathname.startsWith(prefix + '/') || pathname.startsWith(prefix + '?')) {
      return `cache:${prefix}`
    }
  }
  return null
}

// Invalidate on mutating requests
app.use('/api/*', async (c, next) => {
  if (['GET', 'HEAD', 'OPTIONS'].includes(c.req.method)) {
    await next()
    return
  }
  // Mutating method — invalidate matching cache key
  const ck = cacheKeyFor(new URL(c.req.url).pathname)
  if (ck) {
    try { await c.env.CACHE.delete(ck) } catch { /* best effort */ }
  }
  await next()
})

// Serve cached GET responses
for (const prefix of CACHED_PREFIXES) {
  app.get(prefix, async (c) => {
    const ck = `cache:${prefix}`

    // Try KV first
    const cached = await c.env.CACHE.get(ck)
    if (cached) {
      const headers = new Headers({ 'Content-Type': 'application/json', 'X-Cache': 'HIT' })
      return new Response(cached, { headers })
    }

    // Miss → proxy to backend
    const url = new URL(c.req.url)
    const target = `${c.env.API_BASE}${url.pathname}${url.search}`
    let resp: Response
    try {
      resp = await fetch(target, {
        method: 'GET',
        headers: { 'X-Scale-Token': c.env.API_SECRET },
      })
    } catch {
      return c.json({ error: 'backend unreachable' }, 502)
    }

    if (resp.status >= 200 && resp.status < 300) {
      const body = await resp.text()
      // Store in KV (best effort, don't block response)
      c.executionCtx.waitUntil(
        c.env.CACHE.put(ck, body, { expirationTtl: KV_TTL }).catch(() => {})
      )
      const headers = new Headers({ 'Content-Type': 'application/json', 'X-Cache': 'MISS' })
      return new Response(body, { status: resp.status, headers })
    }

    // Non-2xx — forward as-is without caching
    const respHeaders = new Headers(resp.headers)
    respHeaders.delete('content-encoding')
    respHeaders.delete('content-length')
    respHeaders.set('X-Cache', 'BYPASS')
    return new Response(resp.body, { status: resp.status, headers: respHeaders })
  })
}

// ── Upload media vers R2 ──────────────────────────────────────────
// POST /api/upload/media  —  multipart/form-data avec champ "file"
// Retourne { key, url } pour creer ensuite le media via POST /api/posting/medias
const MIME_ALLOW = new Set([
  'image/jpeg', 'image/png', 'image/webp', 'image/gif',
  'video/mp4', 'video/quicktime', 'video/webm',
  'audio/mpeg', 'audio/mp4', 'audio/ogg',
])
const MAX_SIZE = 100 * 1024 * 1024 // 100 MB

app.post('/api/upload/media', async (c) => {
  const form = await c.req.formData()
  const raw = form.get('file')
  if (!raw || typeof raw === 'string') {
    return c.json({ error: 'missing file field' }, 400)
  }
  // Workers runtime: raw is a File (Blob subclass)
  const file = raw as unknown as { name: string; size: number; type: string; stream(): ReadableStream; arrayBuffer(): Promise<ArrayBuffer> }
  if (file.size > MAX_SIZE) {
    return c.json({ error: 'file too large (max 100 MB)' }, 413)
  }
  const ct = file.type || 'application/octet-stream'
  if (!MIME_ALLOW.has(ct)) {
    return c.json({ error: `unsupported type: ${ct}` }, 415)
  }

  // Cle : persona/<uuid>.<ext>
  const ext = file.name?.split('.').pop()?.toLowerCase() || 'bin'
  const personaId = form.get('persona_id') as string | null
  const prefix = personaId ? `p/${personaId}` : 'shared'
  const key = `${prefix}/${crypto.randomUUID()}.${ext}`

  await c.env.MEDIA.put(key, file.stream(), {
    httpMetadata: { contentType: ct },
    customMetadata: {
      original: file.name || 'unknown',
      uploaded: new Date().toISOString(),
    },
  })

  // URL publique servie par le gateway
  const origin = new URL(c.req.url).origin
  const url = `${origin}/media/${key}`

  return c.json({ key, url, content_type: ct, size: file.size })
})

// ── Servir les medias depuis R2 ───────────────────────────────────
// GET /media/*  —  auth via Bearer token OU referer depuis scalelab.win
app.get('/media/*', async (c) => {
  // Auth : accepter soit un Bearer token, soit un referer autorise
  const bearer = c.req.header('Authorization')?.replace('Bearer ', '')
  const referer = c.req.header('Referer') || ''
  const isAuthed = bearer === c.env.API_SECRET
  const isFromApp = referer.includes('scalelab.win') || referer.includes('localhost')

  if (!isAuthed && !isFromApp) {
    return c.json({ error: 'unauthorized' }, 401)
  }

  const key = c.req.path.replace('/media/', '')
  if (!key) return c.json({ error: 'missing key' }, 400)

  const obj = await c.env.MEDIA.get(key)
  if (!obj) return c.json({ error: 'not found' }, 404)

  const headers = new Headers()
  headers.set('Content-Type', obj.httpMetadata?.contentType || 'application/octet-stream')
  headers.set('Cache-Control', 'public, max-age=31536000, immutable')
  headers.set('ETag', obj.httpEtag)

  return new Response(obj.body, { headers })
})

// Proxy /api/* vers le backend VPS via le tunnel
app.all('/api/*', async (c) => {
  const url = new URL(c.req.url)
  const target = `${c.env.API_BASE}${url.pathname}${url.search}`

  const headers: Record<string, string> = {
    'X-Scale-Token': c.env.API_SECRET,
  }
  const ct = c.req.header('Content-Type')
  if (ct) headers['Content-Type'] = ct

  let resp: Response
  try {
    resp = await fetch(target, {
      method: c.req.method,
      headers,
      body: ['GET', 'HEAD'].includes(c.req.method) ? undefined : await c.req.arrayBuffer(),
    })
  } catch {
    return c.json({ error: 'backend unreachable' }, 502)
  }

  // Forward la reponse telle quelle
  const respHeaders = new Headers(resp.headers)
  respHeaders.delete('content-encoding') // evite les problemes de double compression
  respHeaders.delete('content-length')

  return new Response(resp.body, {
    status: resp.status,
    headers: respHeaders,
  })
})

// WebSocket proxy /ws/* vers le backend VPS via le tunnel
// Cloudflare Workers supportent le proxy WebSocket : on fait un fetch avec
// le header Upgrade vers le backend, et on retourne la reponse 101 telle quelle.
// Le Worker relaie automatiquement les frames dans les deux sens.
app.get('/ws/*', async (c) => {
  const upgradeHeader = c.req.header('Upgrade')
  if (!upgradeHeader || upgradeHeader.toLowerCase() !== 'websocket') {
    return c.json({ error: 'expected websocket upgrade' }, 426)
  }

  // Auth : le front passe le token en query param ?token=...
  const url = new URL(c.req.url)
  const wsToken = url.searchParams.get('token')
  if (!wsToken || wsToken !== c.env.API_SECRET) {
    return c.json({ error: 'unauthorized' }, 401)
  }

  // Construire l'URL backend : remplacer le scheme par https et pointer vers le VPS
  const target = `${c.env.API_BASE}${url.pathname}${url.search}`

  let resp: Response
  try {
    resp = await fetch(target, {
      headers: {
        Upgrade: 'websocket',
        'X-Scale-Token': c.env.API_SECRET,
      },
    })
  } catch {
    return c.json({ error: 'backend unreachable (ws)' }, 502)
  }

  // Si le backend n'a pas repondu 101, on forward l'erreur
  if (resp.status !== 101) {
    return c.json({ error: 'backend refused websocket', status: resp.status }, 502)
  }

  // Retourner la reponse 101 telle quelle — Cloudflare Workers relaient les frames
  return new Response(null, {
    status: 101,
    webSocket: (resp as any).webSocket,
  })
})

// Health du gateway lui-meme
app.get('/health', (c) => c.json({ ok: true, layer: 'gateway', ts: Date.now() }))

app.notFound((c) => c.json({ error: 'not found' }, 404))

export default app
