// Only cache draft pages and the assets they need. API writes always go online.
const cacheName = 'kersimmy-draft-pages-v1';
const assets = [
  '/reader-storage.js', '/reader-offline.js', '/glossary-poc.css',
  '/glossary-poc.js', '/dialogs.js',
];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(cacheName).then(cache => cache.addAll(assets)));
});
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));

self.addEventListener('fetch', event => {
  const {request} = event;
  const url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin) return;
  const draft = request.mode === 'navigate' && /^\/books\/[^/]+\/draft$/.test(url.pathname);
  if (!draft && !assets.includes(url.pathname)) return;
  event.respondWith((async () => {
    const cache = await caches.open(cacheName).catch(() => null);
    let response;
    try {
      response = await fetch(request);
    } catch (error) {
      const saved = await cache?.match(url.pathname);
      if (saved) return saved;
      throw error;
    }
    if (cache && response.ok && !response.redirected) {
      try { await cache.put(url.pathname, response.clone()); }
      catch { /* An unavailable cache must not prevent online reading. */ }
    }
    return response;
  })());
});
