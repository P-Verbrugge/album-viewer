// Minimal service worker, just enough to satisfy PWA installability
// criteria. It deliberately only ever touches our own static assets
// (CSS/JS/icons) with a stale-while-revalidate strategy — every API call,
// photo, and video request always goes straight to the network, so nothing
// here can ever show you stale photos or bypass login.
//
// Note: service workers only register in "secure contexts" (HTTPS, or the
// literal hosts "localhost"/"127.0.0.1"). Visiting the app over plain HTTP
// on your LAN IP (e.g. http://192.168.x.x:8080) means the browser won't
// register this at all — that's a browser security rule, not a bug here.
// The manifest/icons still work for "Add to Home Screen" without it.

const CACHE_NAME = "album-viewer-shell-v1";

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  const isOwnStaticAsset =
    event.request.method === "GET" &&
    url.origin === self.location.origin &&
    url.pathname.startsWith("/static/");

  if (!isOwnStaticAsset) {
    return; // let the browser handle everything else normally
  }

  event.respondWith(
    caches.open(CACHE_NAME).then(async (cache) => {
      const cached = await cache.match(event.request);
      const networkFetch = fetch(event.request)
        .then((response) => {
          if (response.ok) cache.put(event.request, response.clone());
          return response;
        })
        .catch(() => cached);
      return cached || networkFetch;
    })
  );
});
