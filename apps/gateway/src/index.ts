import { Hono } from 'hono'
import { cors } from 'hono/cors'

type Env = {
  API_BASE: string
  API_SECRET: string
  CACHE: KVNamespace
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

// Health du gateway lui-meme
app.get('/health', (c) => c.json({ ok: true, layer: 'gateway', ts: Date.now() }))

app.notFound((c) => c.json({ error: 'not found' }, 404))

export default app
