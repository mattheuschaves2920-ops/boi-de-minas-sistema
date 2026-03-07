const CACHE_NAME = "boi-de-minas-pwa-v1";
const urlsToCache = [
  "/",
  "/static/style.css",
  "/static/logo.png",
  "/static/manifest.webmanifest"
];

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(urlsToCache)).catch(() => Promise.resolve())
  );
});

self.addEventListener("fetch", event => {
  if (event.request.method !== "GET") return;
  event.respondWith(
    caches.match(event.request).then(response => response || fetch(event.request))
  );
});
