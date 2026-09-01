"use strict";

/*
 * Service worker для PWA-оболонки Ковадла.
 *
 * Кешує статичну "оболонку" (index.html, manifest, іконки, three.js з CDN)
 * для офлайн-завантаження й швидкого повторного відкриття. /api/* сюди
 * НЕ входить: це виклики до локального Python-сервера (web/server.py),
 * якого на статичному хостингу (GitHub Pages) немає — кешувати чи
 * підміняти їх немає сенсу, нехай ідуть у мережу як є.
 *
 * CACHE_NAME піднімайте (v1 -> v2 -> ...) при кожній суттєвій зміні
 * набору файлів оболонки, щоб activate() прибрав старий кеш.
 */

const CACHE_NAME = "kovadlo-shell-v1";

const CORE_ASSETS = [
  "./",
  "./index.html",
  "./manifest.json",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.min.js",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(CORE_ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin === self.location.origin && url.pathname.includes("/api/")) {
    return; // локальний бекенд — не перехоплюємо
  }

  event.respondWith(
    caches.match(request).then((cached) => {
      const network = fetch(request)
        .then((response) => {
          if (response && response.ok) {
            const copy = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          }
          return response;
        })
        .catch(() => cached); // офлайн і немає в кеші — тут нічого не вдіяти
      return cached || network;
    })
  );
});
