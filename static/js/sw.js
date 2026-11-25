const TILE_CACHE = "local-tiles-v1";

self.addEventListener("install", () => self.skipWaiting());

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Тайлы с нашего сервера: cache-first
  if (url.pathname.startsWith("/tiles/")) {
    event.respondWith(
      caches.open(TILE_CACHE).then(async (cache) => {
        const cached = await cache.match(event.request);
        if (cached) return cached;
        try {
          const res = await fetch(event.request);
          if (res.ok) cache.put(event.request, res.clone());
          return res;
        } catch {
          return new Response("", { status: 404 });
        }
      })
    );
    return;
  }

  // Leaflet-файлы (локальные из static/vendor) — тоже кэшируем
  if (url.pathname.includes("/vendor/leaflet/")) {
    event.respondWith(
      caches.open(TILE_CACHE).then(async (cache) => {
        const cached = await cache.match(event.request);
        if (cached) return cached;
        try {
          const res = await fetch(event.request);
          if (res.ok) cache.put(event.request, res.clone());
          return res;
        } catch {
          return new Response("", { status: 404 });
        }
      })
    );
  }
});