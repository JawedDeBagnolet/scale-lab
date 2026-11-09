// Scale Lab Service Worker — cache JS/CSS/font assets only
const CACHE_NAME = 'sl-v3';

// Assets to precache on install
const PRECACHE = [
  './support.js',
  './api-data.js',
  'https://cdn.jsdelivr.net/npm/@phosphor-icons/web@2.1.1/src/regular/style.css',
  'https://cdn.jsdelivr.net/npm/@phosphor-icons/web@2.1.1/src/fill/style.css',
  'https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700&family=Geist+Mono:wght@400;500&display=swap',
];

// Only cache these extensions — never HTML (Safari breaks on redirected SW responses)
const CACHEABLE_EXT = /\.(js|css|woff2?|ttf|eot|png|svg|ico)(\?|$)/i;

// Install — precache core assets
self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting())
  );
});

// Activate — clean old caches, claim clients immediately
self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((names) =>
      Promise.all(names.filter((n) => n !== CACHE_NAME).map((n) => caches.delete(n)))
    ).then(() => self.clients.claim())
  );
});

// Fetch — stale-while-revalidate for static assets only
self.addEventListener('fetch', (e) => {
  // Only GET requests
  if (e.request.method !== 'GET') return;

  const url = new URL(e.request.url);

  // Skip API, auth, websocket, media
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/auth/') ||
      url.pathname.startsWith('/ws/') || url.pathname.startsWith('/media/')) {
    return;
  }

  // Skip HTML pages — let them go straight to network (fixes Safari redirect error)
  if (e.request.mode === 'navigate' || url.pathname.endsWith('.html') || url.pathname.endsWith('.dc')) {
    return;
  }

  // Only cache known static asset types + CDN resources
  const isCDN = url.hostname !== location.hostname;
  if (!isCDN && !CACHEABLE_EXT.test(url.pathname)) return;

  // Stale-while-revalidate for static assets
  e.respondWith(
    caches.open(CACHE_NAME).then((cache) =>
      cache.match(e.request).then((cached) => {
        const fetchPromise = fetch(e.request).then((response) => {
          if (response && response.status === 200 && response.type !== 'opaqueredirect') {
            cache.put(e.request, response.clone());
          }
          return response;
        }).catch(() => cached);

        return cached || fetchPromise;
      })
    )
  );
});

// Message handler — force update
self.addEventListener('message', (e) => {
  if (e.data === 'skipWaiting') self.skipWaiting();
  if (e.data === 'clearCache') {
    caches.delete(CACHE_NAME).then(() => {
      caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE));
    });
  }
});
