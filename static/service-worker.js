const CACHE_NAME = 'boi-minas-v1';

const urlsToCache = [
    '/',
    '/login',
    '/static/style.css',
    '/static/icon-192.png',
    '/static/icon-512.png'
];

self.addEventListener('install', event => {

    event.waitUntil(

        caches.open(CACHE_NAME)
            .then(cache => {
                return cache.addAll(urlsToCache);
            })
    );
});

self.addEventListener('fetch', event => {

    event.respondWith(

        caches.match(event.request)
            .then(response => {
                return response || fetch(event.request);
            })
    );
});
