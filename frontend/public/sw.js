const CACHE_NAME = "nova-ai-pwa-v3";
const APP_SHELL = [
  "/",
  "/manifest.json",
  "/favicon.svg",
  "/favicon.ico",
  "/icons/nova-star-16x16.png",
  "/icons/nova-star-32x32.png",
  "/icons/nova-star-192x192.png",
  "/icons/nova-star-512x512.png",
  "/icons/nova-star-maskable-192x192.png",
  "/icons/nova-star-maskable-512x512.png",
  "/icons/nova-star-apple-touch.png",
  "/icons/nova-star-splash-512x512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) =>
      Promise.all(
        cacheNames
          .filter((cacheName) => cacheName !== CACHE_NAME)
          .map((cacheName) => caches.delete(cacheName))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") {
    return;
  }

  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});
