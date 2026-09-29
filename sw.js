// Service worker for the Alpine hydrant map.
// Strategy: network-first, falling back to a cached copy when there is no
// network. Every successful response is cached as it goes by, so the map
// keeps working offline after at least one normal (online) visit.
const CACHE = 'alpine-hydrant-map-v2';

// The page passes its own exact URL as a query string when it registers
// this worker (see the <script> near the end of the HTML). That's the only
// reliable way to know what the page is actually called — hardcoding a
// filename here breaks if the file is renamed (e.g. to index.html) on
// whatever host it's deployed to, which is exactly what caused installed
// shortcuts to 404 on start_url.
const params = new URLSearchParams(self.location.search);
const pageParam = params.get('page');
const PAGE_URL = pageParam ? new URL(pageParam, self.location).toString() : null;

// The manifest itself is now built at runtime as a Blob URL (see the HTML),
// so there's no fixed manifest file to precache — just the icon it points
// at, plus the page.
const PRECACHE = ['./hydrant-icon.png']
  .map((u) => new URL(u, self.registration.scope).toString());
if (PAGE_URL) PRECACHE.push(PAGE_URL);

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) =>
      // Cache each URL independently (not cache.addAll, which is all-or-
      // nothing) so one missing file doesn't stop the rest from caching.
      Promise.all(PRECACHE.map((u) =>
        fetch(u).then((r) => { if (r.ok) return c.put(u, r); }).catch(() => {})
      ))
    ).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  if (e.request.method !== 'GET') return;

  e.respondWith(
    // {cache:'no-store'} bypasses the browser's own HTTP cache, not just
    // ours. Without it, "network-first" can still be quietly satisfied by
    // a same-device HTTP cache honoring the host's Cache-Control header
    // (GitHub Pages/Fastly send a several-minute max-age), so a page that
    // was reopened soon after a new deploy could still see old content
    // even though this code did ask the network first.
    fetch(e.request, { cache: 'no-store' }).then((res) => {
      // Only cache good, basic (same-origin, non-opaque) responses.
      if (res && res.ok && res.type === 'basic') {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy));
      }
      return res;
    }).catch(() =>
      caches.match(e.request).then((cached) => {
        if (cached) return cached;
        // Navigating to the page itself with nothing cached yet and no
        // network: nothing we can do, let the browser show its own
        // offline error.
        throw new Error('offline and not yet cached');
      })
    )
  );
});
