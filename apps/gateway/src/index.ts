import { Hono } from 'hono'
import { cors } from 'hono/cors'

type Env = {
  API_BASE: string
  API_SECRET: string
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
// GET /media/*  —  pas d'auth, les URLs sont difficiles a deviner (UUID)
app.get('/media/*', async (c) => {
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

  const url = new URL(c.req.url)
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
