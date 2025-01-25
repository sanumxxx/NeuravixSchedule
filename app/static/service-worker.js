// service-worker.js

const CACHE_NAME = 'melgu-schedule-v1';

// Основные ресурсы для кэширования
const STATIC_RESOURCES = [
    '/static/manifest.json',
    '/static/offline.html',
    // Android иконки
    '/static/android/android-launchericon-512-512.png',
    '/static/android/android-launchericon-192-192.png',
    '/static/android/android-launchericon-144-144.png',
    '/static/android/android-launchericon-96-96.png',
    '/static/android/android-launchericon-72-72.png',
    '/static/android/android-launchericon-48-48.png',
    // iOS иконки
    '/static/ios/180.png',
    '/static/ios/1024.png'
];

// URLs расписания для кэширования
const SCHEDULE_PATHS = [
    '/timetable',
    '/api/schedule'
];

// Установка Service Worker
self.addEventListener('install', (event) => {
    console.log('[ServiceWorker] Install');
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => {
                console.log('[ServiceWorker] Caching static resources');
                return cache.addAll(STATIC_RESOURCES);
            })
            .then(() => {
                console.log('[ServiceWorker] Skip waiting');
                return self.skipWaiting();
            })
            .catch((error) => {
                console.error('[ServiceWorker] Install failed:', error);
            })
    );
});

// Активация Service Worker
self.addEventListener('activate', (event) => {
    console.log('[ServiceWorker] Activate');
    event.waitUntil(
        Promise.all([
            // Удаляем старые версии кэша
            caches.keys().then((cacheNames) => {
                return Promise.all(
                    cacheNames.map((cacheName) => {
                        if (cacheName !== CACHE_NAME) {
                            console.log('[ServiceWorker] Removing old cache:', cacheName);
                            return caches.delete(cacheName);
                        }
                    })
                );
            }),
            // Захватываем клиентов
            self.clients.claim()
        ])
    );
});

// Проверяем, является ли запрос запросом расписания
function isScheduleRequest(url) {
    return SCHEDULE_PATHS.some(path => url.pathname.startsWith(path));
}

// Проверяем, является ли запрос API запросом
function isApiRequest(url) {
    return url.pathname.startsWith('/api/');
}

// Основная функция обработки запросов
async function handleFetch(event) {
    const request = event.request;
    const url = new URL(request.url);

    try {
        // Для запросов расписания используем Network First
        if (isScheduleRequest(url)) {
            try {
                const networkResponse = await fetch(request);
                if (networkResponse.ok) {
                    const cache = await caches.open(CACHE_NAME);
                    await cache.put(request, networkResponse.clone());
                    return networkResponse;
                }
            } catch (error) {
                const cachedResponse = await caches.match(request);
                if (cachedResponse) {
                    return cachedResponse;
                }
                // Если нет в кэше, показываем офлайн страницу
                return caches.match('/static/offline.html');
            }
        }

        // Для API запросов
        if (isApiRequest(url)) {
            try {
                return await fetch(request);
            } catch (error) {
                const cachedResponse = await caches.match(request);
                if (cachedResponse) {
                    return cachedResponse;
                }
                return new Response(
                    JSON.stringify({ error: 'Нет подключения к сети' }),
                    {
                        status: 503,
                        headers: { 'Content-Type': 'application/json' }
                    }
                );
            }
        }

        // Для статических ресурсов используем Cache First
        if (STATIC_RESOURCES.includes(url.pathname)) {
            const cachedResponse = await caches.match(request);
            if (cachedResponse) {
                return cachedResponse;
            }
        }

        // Для остальных запросов пробуем сеть
        try {
            const networkResponse = await fetch(request);
            if (networkResponse.ok && request.method === 'GET') {
                const cache = await caches.open(CACHE_NAME);
                await cache.put(request, networkResponse.clone());
            }
            return networkResponse;
        } catch (error) {
            const cachedResponse = await caches.match(request);
            if (cachedResponse) {
                return cachedResponse;
            }
            // Для навигационных запросов показываем офлайн страницу
            if (request.mode === 'navigate') {
                return caches.match('/static/offline.html');
            }
            throw error;
        }
    } catch (error) {
        console.error('[ServiceWorker] Fetch error:', error);
        // Для навигационных запросов всегда показываем офлайн страницу
        if (request.mode === 'navigate') {
            return caches.match('/static/offline.html');
        }
        // Для остальных возвращаем ошибку
        return new Response('Офлайн режим', { status: 503 });
    }
}

// Перехват запросов
self.addEventListener('fetch', (event) => {
    event.respondWith(handleFetch(event));
});

// Обработка push-уведомлений
self.addEventListener('push', (event) => {
    if (event.data) {
        const options = {
            body: event.data.text(),
            icon: '/static/android/android-launchericon-192-192.png',
            badge: '/static/android/android-launchericon-72-72.png',
            vibrate: [100, 50, 100],
            data: {
                dateOfArrival: Date.now(),
                primaryKey: 1
            }
        };

        event.waitUntil(
            self.registration.showNotification('Расписание МелГУ', options)
        );
    }
});

// Обработка клика по уведомлению
self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    event.waitUntil(
        clients.openWindow('/')
    );
});