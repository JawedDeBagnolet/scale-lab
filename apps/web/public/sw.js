// Scale Lab Service Worker — cache all static assets for instant navigation
const CACHE_NAME = 'sl-v1';

// Assets to precache on install
const PRECACHE = [
  './support.js',
  './api-data.js',
  'https://cdn.jsdelivr.net/npm/@phosphor-icons/web@2.1.1/src/regular/style.css',
  'https://cdn.jsdelivr.net/npm/@phosphor-icons/web@2.1.1/src/fill/style.css',
  'https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700&family=Geist+Mono:wght@400;500&display=swap',
];

// DC module files — precached after install via message
const DC_MODULES = [
  'Module%20Dashboard%20v1.dc.html',
  'Module%20Comptes%20v1.dc.html',
  'Module%20Personas%20v1.dc.html',
  'Module%20Posting%20v1.dc.html',
  'Module%20Veille%20v1.dc.html',
  'Module%20Statistiques%20v1.dc.html',
  'Module%20CRM%20v1.dc.html',
  'Module%20Liens%20v1.dc.html',
  'Module%20Logs%20v1.dc.html',
  'Module%20Targets%20v1.dc.html',
  'Module%20Scenarios%20v1.dc.html',
  'Module%20Comportements%20v1.dc.html',
  'Module%20Proxies%20v1.dc.html',
  'Module%20Parc%20iPhone%20v1.dc.html',
  'Module%20Parametres%20v1.dc.html',
];

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
  // Background-cache all DC modules
  caches.open(CACHE_NAME).then((cache) => {
    DC_MODULES.forEach((m) => {
      cache.match(m).then((r) => { if (!r) cache.add(m).catch(() => {}); });
    });
  });
});

// Fetch — stale-while-revalidate for static assets, network-first for API
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);

  // API calls — always network (data freshness matters)
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/auth/') ||
      url.pathname.startsWith('/ws/') || url.pathname.startsWith('/media/')) {
    return; // let browser handle normally
  }

  // Static assets — stale-while-revalidate
  // Serve from cache immediately, update cache in background
  e.respondWith(
    caches.open(CACHE_NAME).then((cache) =>
      cache.match(e.request).then((cached) => {
        const fetchPromise = fetch(e.request).then((response) => {
          // Only cache successful responses
          if (response && response.status === 200) {
            cache.put(e.request, response.clone());
          }
          return response;
        }).catch(() => cached); // offline fallback to cache

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
