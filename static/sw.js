const CACHE = 'caine-v2';
const PRECACHE = [
  '/static/offline.html',
  '/static/icon-512.jpg',
  '/static/icon-192.jpg',
  '/static/favicon.ico',
  '/static/manifest.json',
];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(PRECACHE)));
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', e => {
  // navigation requests (loading pages) — show offline page if no network
  if (e.request.mode === 'navigate') {
    e.respondWith(
      fetch(e.request).catch(() => caches.match('/static/offline.html'))
    );
    return;
  }
  // static assets — cache first
  if (e.request.url.includes('/static/')) {
    e.respondWith(
      caches.match(e.request).then(r => r || fetch(e.request).then(resp => {
        const clone = resp.clone();
        caches.open(CACHE).then(c => c.put(e.request, clone));
        return resp;
      }))
    );
    return;
  }
  // API calls (/chat, /state, etc.) — network only, no caching
  e.respondWith(fetch(e.request));
});
